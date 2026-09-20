"""Background execution of the pipeline, in a dedicated QThread.

Downloading, transcribing, aligning and rendering are long blocking operations:
they must NEVER run on the UI thread, which they would freeze. This worker runs
them in a secondary thread and communicates only through Qt signals, so that no
widget is ever touched from here.
"""

from __future__ import annotations

import queue

from PySide6.QtCore import QThread, Signal

from ..config import Config
from ..events import PipelineEvent
from ..forced_aligner import AlignedLine
from ..pipeline import VideoLyricsPipeline
from .gui_review_provider import GuiReviewProvider


class PipelineWorker(QThread):
    """Run `VideoLyricsPipeline.run()` off the UI thread."""

    event_received = Signal(object)
    alignment_ready = Signal(object)
    finished_ok = Signal(str)
    finished_error = Signal(str)

    def __init__(
        self,
        youtube_url: str,
        config: Config,
        review_provider: GuiReviewProvider,
    ) -> None:
        super().__init__()
        self.youtube_url = youtube_url
        self.config = config
        self.review_provider = review_provider
        self._alignment_queue: queue.Queue[list[AlignedLine]] = queue.Queue(maxsize=1)

    def run(self) -> None:
        try:
            pipeline = VideoLyricsPipeline(
                self.config, review_provider=self.review_provider
            )
            final_path = pipeline.run(
                self.youtube_url,
                on_event=self._on_event,
                alignment_gate=self._alignment_gate,
            )
            self.finished_ok.emit(str(final_path))
        except Exception as exc:
            self.finished_error.emit(str(exc))

    def submit_alignment(self, lines: list[AlignedLine]) -> None:
        """Called from the UI thread on the render click: releases the worker."""
        self._alignment_queue.put(lines)

    def _on_event(self, event: PipelineEvent) -> None:
        """Pipeline callback turned into a Qt signal, which crosses threads."""
        self.event_received.emit(event)

    def _alignment_gate(self, lines: list[AlignedLine]) -> list[AlignedLine]:
        """Block the worker while the alignment is reviewed in the UI."""
        self.alignment_ready.emit(lines)
        return self._alignment_queue.get()
