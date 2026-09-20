"""Final render: gaussian blur plus lyrics burned into the picture, via ffmpeg.

A single ffmpeg pass applies ``gblur`` and then one ``drawtext`` filter per cue.
There is never a separate subtitle track. The ``-progress`` output of ffmpeg is
parsed to emit `PipelineEvent(RENDER, PROGRESS)`.

The filtergraph is written to a file and passed with ``-filter_complex_script``
to avoid shell quoting problems, and each lyrics line goes to its own text file
read back by ``drawtext``, which removes any escaping concern for apostrophes,
commas or percent signs.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .config import Config
from .events import PipelineEvent, PipelineStep, StepStatus
from .subtitle_builder import DrawTextCue
from .utils import ffmpeg_utils
from .utils.logger import get_logger

logger = get_logger("renderer")

EventCallback = Callable[[PipelineEvent], None]

_NVENC_CODECS = ("h264_nvenc", "hevc_nvenc")
_NVENC_PRESETS = frozenset(
    {
        "p1",
        "p2",
        "p3",
        "p4",
        "p5",
        "p6",
        "p7",
        "slow",
        "medium",
        "fast",
        "hp",
        "hq",
        "ll",
        "llhq",
        "llhp",
        "default",
    }
)
_NVENC_DEFAULT_PRESET = "p5"


class RenderError(RuntimeError):
    """The video render failed."""


@dataclass
class RenderResult:
    """Where the rendered video landed, and how long it is."""

    output_path: Path
    duration_seconds: float


def _quote(value: str) -> str:
    """Quote a control value for the ffmpeg filtergraph.

    Reserved for the values WE generate, namely font and text file paths and
    alpha or enable expressions. Lyrics never go through here: they are passed
    to drawtext through ``textfile``. Backslashes, colons (which must be escaped
    even inside quotes, as in the Windows drive letter ``C\\:``) and percent
    signs are neutralised.
    """
    escaped = value.replace("\\", "\\\\").replace(":", "\\:").replace("%", "\\%")
    return f"'{escaped}'"


def _forward_slashes(path: Path | str) -> str:
    """Path with forward slashes, which ffmpeg accepts on every platform."""
    return str(path).replace("\\", "/")


class VideoRenderer:
    """Apply the blur and burn the lyrics in, through a single ffmpeg pass."""

    def __init__(self, config: Config) -> None:
        subtitles = config.subtitles
        video = config.video

        self.font_path = config.resolve_path(
            subtitles.get("font_path", "./assets/fonts/Montserrat-Bold.ttf")
        )
        self.font_size = int(subtitles.get("font_size", 54))
        self.font_color = subtitles.get("font_color", "white")
        self.outline_color = subtitles.get("outline_color", "black")
        self.outline_width = int(subtitles.get("outline_width", 3))
        self.position = subtitles.get("position", "bottom")
        self.margin = int(subtitles.get("margin_px", 150))
        self.fade = max(float(subtitles.get("fade_ms", 150)) / 1000.0, 0.0)

        blur = video.get("blur", {})
        self.blur_filter = blur.get("filter", "gblur")
        self.blur_sigma = float(blur.get("sigma", 20))
        self.output_dir = config.resolve_path(
            video.get("output_dir", "./outputs/final")
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.codec = video.get("codec", "libx264")
        self.crf = int(video.get("crf", 18))
        self.preset = video.get("preset", "medium")
        self.copy_audio = bool(video.get("copy_audio", True))

    def render(
        self,
        video_path: Path,
        cues: list[DrawTextCue],
        *,
        output_name: str | None = None,
        on_event: EventCallback | None = None,
    ) -> RenderResult:
        """Render the blurred video with the lyrics burned in.

        Args:
            video_path: The downloaded source video.
            cues: Timestamped text cues coming from `SubtitleBuilder`.
            output_name: Output file name, ``<stem>_lyrics.mp4`` by default.
            on_event: Progress callback.
        """
        ffmpeg_utils.ensure_ffmpeg()
        if not self.font_path.exists():
            raise RenderError(
                f"Font not found: {self.font_path}. Put a .ttf or .otf file in "
                f"assets/fonts/ and set subtitles.font_path in config.yaml."
            )

        self._emit(
            on_event, StepStatus.STARTED, "Rendering with ffmpeg.", progress_pct=0.0
        )

        duration = ffmpeg_utils.probe_duration(video_path)
        output_path = self.output_dir / (output_name or f"{video_path.stem}_lyrics.mp4")

        text_dir = output_path.parent / f".{output_path.stem}_texts"
        script_path = output_path.with_suffix(".filtergraph.txt")
        script_path.write_text(
            self._build_filtergraph(cues, text_dir), encoding="utf-8"
        )

        args = [
            "-i",
            str(video_path),
            "-filter_complex_script",
            str(script_path),
            "-map",
            "[v]",
        ]
        if self.copy_audio:
            args += ["-map", "0:a?", "-c:a", "aac", "-b:a", "192k"]
        args += self._encoder_args()
        args += ["-pix_fmt", "yuv420p", str(output_path)]

        def report(pct: float) -> None:
            self._emit(on_event, StepStatus.PROGRESS, "Rendering.", progress_pct=pct)

        try:
            ffmpeg_utils.run_with_progress(
                args, total_duration=duration, on_progress=report
            )
        except ffmpeg_utils.FFmpegError as exc:
            self._emit(on_event, StepStatus.FAILED, str(exc))
            raise RenderError(str(exc)) from exc
        finally:
            script_path.unlink(missing_ok=True)
            shutil.rmtree(text_dir, ignore_errors=True)

        self._emit(
            on_event,
            StepStatus.COMPLETED,
            f"Video rendered: {output_path.name}",
            progress_pct=100.0,
        )
        logger.info("Render finished: %s", output_path)
        return RenderResult(output_path=output_path, duration_seconds=duration)

    def _encoder_args(self) -> list[str]:
        """Video encoding arguments for the configured codec.

        ``libx264`` runs on the CPU and uses the usual ``-crf`` and ``-preset``.
        The NVENC encoders have no ``-crf``: constant quality is expressed as
        ``-cq`` in VBR mode with no bitrate target.
        """
        if self.codec in _NVENC_CODECS:
            preset = (
                self.preset if self.preset in _NVENC_PRESETS else _NVENC_DEFAULT_PRESET
            )
            return [
                "-c:v",
                self.codec,
                "-preset",
                preset,
                "-rc",
                "vbr",
                "-cq",
                str(self.crf),
                "-b:v",
                "0",
            ]
        return ["-c:v", self.codec, "-crf", str(self.crf), "-preset", self.preset]

    def _y_expression(self) -> str:
        """The drawtext ``y`` expression for the configured position."""
        if self.position == "top":
            return str(self.margin)
        if self.position == "center":
            return "(h-text_h)/2"
        return f"h-text_h-{self.margin}"

    def _alpha_expression(self, start: float, end: float) -> str:
        """Alpha expression fading the text in and out over `fade` seconds."""
        if self.fade <= 0:
            return "1"
        fade = self.fade
        return (
            f"if(lt(t,{start}),0,"
            f"if(lt(t,{start + fade}),(t-{start})/{fade},"
            f"if(lt(t,{end - fade}),1,"
            f"if(lt(t,{end}),({end}-t)/{fade},0))))"
        )

    def _drawtext(self, cue: DrawTextCue, textfile_path: Path) -> str:
        """Build the drawtext filter for one cue."""
        options = [
            f"fontfile={_quote(_forward_slashes(self.font_path))}",
            f"textfile={_quote(_forward_slashes(textfile_path))}",
            f"fontsize={self.font_size}",
            f"fontcolor={self.font_color}",
            f"borderw={self.outline_width}",
            f"bordercolor={self.outline_color}",
            "x=(w-text_w)/2",
            f"y={self._y_expression()}",
            f"alpha={_quote(self._alpha_expression(cue.start, cue.end))}",
            f"enable={_quote(f'between(t,{cue.start},{cue.end})')}",
        ]
        return "drawtext=" + ":".join(options)

    def _build_filtergraph(self, cues: list[DrawTextCue], text_dir: Path) -> str:
        """Assemble ``[0:v] gblur, drawtext, drawtext, ... [v]``.

        The text of every cue is written to its own file under `text_dir`, which
        drawtext reads through ``textfile``.
        """
        text_dir.mkdir(parents=True, exist_ok=True)
        chain = [f"{self.blur_filter}=sigma={self.blur_sigma}"]
        for index, cue in enumerate(cues):
            text_file = text_dir / f"cue_{index:04d}.txt"
            text_file.write_text(cue.text, encoding="utf-8", newline="")
            chain.append(self._drawtext(cue, text_file))
        return "[0:v]" + ",".join(chain) + "[v]"

    @staticmethod
    def _emit(
        cb: EventCallback | None,
        status: StepStatus,
        message: str,
        *,
        progress_pct: float | None = None,
    ) -> None:
        if cb is not None:
            cb(
                PipelineEvent(
                    PipelineStep.RENDER, status, message, progress_pct=progress_pct
                )
            )
