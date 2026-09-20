"""Pipeline progress events.

Every exchange between the pipeline and the outside world (desktop UI or CLI
logs) goes through typed events, so that the business logic is never coupled to
Qt and the tests never depend on a particular presentation layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class PipelineStep(Enum):
    """Ordered steps of the video pipeline."""

    DOWNLOAD = auto()
    LYRICS_FETCH = auto()
    REVIEW = auto()
    FORCED_ALIGNMENT = auto()
    SUBTITLE_BUILD = auto()
    RENDER = auto()


class StepStatus(Enum):
    """State of a step at a given moment."""

    STARTED = auto()
    PROGRESS = auto()
    COMPLETED = auto()
    FAILED = auto()


@dataclass
class PipelineEvent:
    """A state change of one pipeline step.

    Attributes:
        step: The step concerned.
        status: The new state of that step.
        message: Short human readable message, shown in logs and in the UI.
        progress_pct: Progress between 0 and 100 when the step reports it.
        payload: Step specific extra data. For ``REVIEW``:
            ``{"raw_text": str, "track_id": str}``.
    """

    step: PipelineStep
    status: StepStatus
    message: str = ""
    progress_pct: float | None = None
    payload: dict | None = None

    def __str__(self) -> str:
        pct = f" {self.progress_pct:.0f}%" if self.progress_pct is not None else ""
        message = f" {self.message}" if self.message else ""
        return f"[{self.step.name}/{self.status.name}{pct}]{message}"
