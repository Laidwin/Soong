"""Turn aligned verses into the display cues consumed by the renderer.

`AlignedLine` objects carry the real timing produced by forced alignment;
`DrawTextCue` is the unit `renderer.py` maps onto ffmpeg `drawtext` filters.
There is never a separate subtitle track: the text is burned into the pixels.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .config import Config
from .events import PipelineEvent, PipelineStep, StepStatus
from .forced_aligner import AlignedLine

EventCallback = Callable[[PipelineEvent], None]


@dataclass
class DrawTextCue:
    """A piece of text to display between `start` and `end`, in seconds."""

    text: str
    start: float
    end: float


class SubtitleBuilder:
    """Convert aligned verses into ordered display cues."""

    def __init__(self, config: Config) -> None:
        subtitles = config.subtitles
        self.mode = subtitles.get("mode", "line")
        self.min_cue_duration = (
            float(subtitles.get("min_cue_duration_ms", 400)) / 1000.0
        )

    def build(
        self,
        lines: list[AlignedLine],
        on_event: EventCallback | None = None,
    ) -> list[DrawTextCue]:
        """Build the ordered list of cues for the configured mode."""
        self._emit(
            on_event, StepStatus.STARTED, f"Building subtitles in {self.mode} mode."
        )

        cues = (
            self._build_word(lines) if self.mode == "word" else self._build_line(lines)
        )
        cues = self._sanitize(cues)

        self._emit(on_event, StepStatus.COMPLETED, f"{len(cues)} cues generated.")
        return cues

    @staticmethod
    def _build_line(lines: list[AlignedLine]) -> list[DrawTextCue]:
        return [
            DrawTextCue(text=line.text, start=line.start, end=line.end)
            for line in lines
        ]

    @staticmethod
    def _build_word(lines: list[AlignedLine]) -> list[DrawTextCue]:
        return [
            DrawTextCue(text=word.text, start=word.start, end=word.end)
            for line in lines
            for word in line.words
        ]

    def _sanitize(self, cues: list[DrawTextCue]) -> list[DrawTextCue]:
        """Drop empty cues, sort by start time and enforce a minimum duration."""
        ordered = sorted(
            (cue for cue in cues if cue.text.strip()), key=lambda cue: cue.start
        )
        return [
            DrawTextCue(
                text=cue.text.strip(),
                start=cue.start,
                end=max(cue.end, cue.start + self.min_cue_duration),
            )
            for cue in ordered
        ]

    @staticmethod
    def _emit(cb: EventCallback | None, status: StepStatus, message: str) -> None:
        if cb is not None:
            cb(PipelineEvent(PipelineStep.SUBTITLE_BUILD, status, message))
