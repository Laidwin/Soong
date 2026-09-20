"""Orchestrator of the lyrics overlay video pipeline.

Chains download, lyrics retrieval, human review when the text comes from the
fallback, forced alignment, subtitle building and the ffmpeg render.

It knows ONLY the `ReviewProvider` and `PipelineEvent` abstractions: no PySide6
import here, so the command line stays usable without any UI dependency.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from .config import Config
from .downloader import VideoDownloader
from .events import PipelineEvent, PipelineStep, StepStatus
from .forced_aligner import AlignedLine, ForcedAligner, ForcedAlignmentError
from .lyrics_source import SOURCE_TRANSCRIPTION, LyricsResult, LyricsSource
from .renderer import VideoRenderer
from .review_provider import ReviewProvider
from .subtitle_builder import SubtitleBuilder
from .utils.logger import get_logger

logger = get_logger("pipeline")

EventCallback = Callable[[PipelineEvent], None]
AlignmentGate = Callable[[list[AlignedLine]], list[AlignedLine]]


class VideoLyricsPipeline:
    """End to end pipeline, event driven and with an injected `ReviewProvider`."""

    def __init__(self, config: Config, review_provider: ReviewProvider) -> None:
        self.config = config
        self.review_provider = review_provider
        self.downloader = VideoDownloader(config)
        self.lyrics_source = LyricsSource(config)
        self.forced_aligner = ForcedAligner(config)
        self.subtitle_builder = SubtitleBuilder(config)
        self.renderer = VideoRenderer(config)
        self.require_manual_review = bool(
            config.review.get("require_manual_review", True)
        )

    def run(
        self,
        youtube_url: str,
        on_event: EventCallback | None = None,
        *,
        alignment_gate: AlignmentGate | None = None,
    ) -> Path:
        """Run the whole pipeline and return the path of the final video.

        Args:
            youtube_url: URL of the clip to process.
            on_event: Progress callback, optional on the command line and always
                provided by the desktop UI.
            alignment_gate: Optional quality gate called with the aligned lines
                before the render. It may block and may alter the lines.
        """
        download = self.downloader.download(youtube_url, on_event=on_event)

        lyrics = self.lyrics_source.fetch(
            download.title, download.artist, download.audio_path, on_event=on_event
        )

        text = self._review(lyrics, on_event)

        aligned_lines = self._align(
            download.audio_path, text, download.duration_seconds, on_event
        )
        if alignment_gate is not None:
            aligned_lines = alignment_gate(aligned_lines)

        cues = self.subtitle_builder.build(aligned_lines, on_event=on_event)

        result = self.renderer.render(
            download.video_path,
            cues,
            output_name=f"{lyrics.track_id}.mp4",
            on_event=on_event,
        )
        logger.info("Pipeline finished: %s", result.output_path)
        return result.output_path

    def _review(self, lyrics: LyricsResult, on_event: EventCallback | None) -> str:
        """Run the human review when the text did not come from Genius."""
        mandatory = lyrics.source == SOURCE_TRANSCRIPTION and self.require_manual_review
        if not (lyrics.needs_review or mandatory):
            self._emit(
                on_event,
                PipelineStep.REVIEW,
                StepStatus.COMPLETED,
                "Reliable lyrics from Genius: no review needed.",
            )
            return lyrics.text

        self._emit(
            on_event,
            PipelineStep.REVIEW,
            StepStatus.STARTED,
            "Waiting for the lyrics to be validated.",
            payload={"raw_text": lyrics.text, "track_id": lyrics.track_id},
        )
        validated = self.review_provider.request_review(lyrics.text, lyrics.track_id)
        self._emit(
            on_event, PipelineStep.REVIEW, StepStatus.COMPLETED, "Lyrics validated."
        )
        return validated

    def _align(
        self,
        audio_path: Path,
        text: str,
        duration: float,
        on_event: EventCallback | None,
    ) -> list[AlignedLine]:
        """Align the text, falling back to a proportional split on failure."""
        try:
            words = self.forced_aligner.align(audio_path, text, on_event=on_event)
            lines = self.forced_aligner.group_into_lines(
                words, text, total_duration=duration
            )
            self._emit(
                on_event,
                PipelineStep.FORCED_ALIGNMENT,
                StepStatus.COMPLETED,
                f"{len(lines)} verses aligned.",
                progress_pct=100.0,
            )
            return lines
        except ForcedAlignmentError as exc:
            logger.warning("Forced alignment failed (%s): falling back.", exc)
            self._emit(
                on_event,
                PipelineStep.FORCED_ALIGNMENT,
                StepStatus.PROGRESS,
                "Forced alignment unavailable: spreading verses proportionally.",
            )
            lines = ForcedAligner.proportional_alignment(text, duration)
            self._emit(
                on_event,
                PipelineStep.FORCED_ALIGNMENT,
                StepStatus.COMPLETED,
                f"{len(lines)} verses placed proportionally.",
                progress_pct=100.0,
            )
            return lines

    @staticmethod
    def _emit(
        cb: EventCallback | None,
        step: PipelineStep,
        status: StepStatus,
        message: str = "",
        *,
        progress_pct: float | None = None,
        payload: dict | None = None,
    ) -> None:
        if cb is not None:
            cb(PipelineEvent(step, status, message, progress_pct, payload))
