"""Screen tracking the progress of every pipeline step in real time."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..events import PipelineEvent, PipelineStep, StepStatus

_STEP_LABELS: list[tuple[PipelineStep, str]] = [
    (PipelineStep.DOWNLOAD, "Download"),
    (PipelineStep.LYRICS_FETCH, "Lyrics retrieval"),
    (PipelineStep.REVIEW, "Human validation"),
    (PipelineStep.FORCED_ALIGNMENT, "Forced alignment"),
    (PipelineStep.SUBTITLE_BUILD, "Subtitles"),
    (PipelineStep.RENDER, "Video render"),
]

_PENDING_MARKER = "..."
_STATUS_MARKERS = {
    StepStatus.STARTED: ">",
    StepStatus.PROGRESS: ">",
    StepStatus.COMPLETED: "OK",
    StepStatus.FAILED: "FAIL",
}


class _StepRow(QWidget):
    """One step line: a status marker next to its label."""

    def __init__(self, label: str) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        self.marker = QLabel(_PENDING_MARKER)
        self.marker.setFixedWidth(40)
        self.marker.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.marker)
        layout.addWidget(QLabel(label))
        layout.addStretch(1)

    def set_status(self, status: StepStatus) -> None:
        self.marker.setText(_STATUS_MARKERS.get(status, _PENDING_MARKER))

    def reset(self) -> None:
        self.marker.setText(_PENDING_MARKER)


class ProgressWidget(QWidget):
    """Step list, progress bar and scrolling log view."""

    def __init__(self) -> None:
        super().__init__()
        self._rows: dict[PipelineStep, _StepRow] = {}
        self._build_ui()

    def reset(self) -> None:
        """Clear every step marker, the progress bar and the log view."""
        for row in self._rows.values():
            row.reset()
        self.progress_bar.setValue(0)
        self.log_view.clear()

    def on_event(self, event: PipelineEvent) -> None:
        """Refresh the UI from a `PipelineEvent`, on the UI thread."""
        row = self._rows.get(event.step)
        if row is not None:
            row.set_status(event.status)
        if event.progress_pct is not None:
            self.progress_bar.setValue(int(event.progress_pct))
        elif event.status == StepStatus.COMPLETED:
            self.progress_bar.setValue(0)
        self.append_log(str(event))

    def append_log(self, line: str) -> None:
        """Append one line to the log view and scroll to the bottom."""
        self.log_view.append(line)
        scrollbar = self.log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("Pipeline progress")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        steps_frame = QFrame()
        steps_frame.setFrameShape(QFrame.Shape.StyledPanel)
        steps_layout = QVBoxLayout(steps_frame)
        for step, label in _STEP_LABELS:
            row = _StepRow(label)
            self._rows[step] = row
            steps_layout.addWidget(row)
        layout.addWidget(steps_frame)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")
        layout.addWidget(self.progress_bar)

        logs_label = QLabel("Log")
        logs_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(logs_label)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet(
            "font-family: Consolas, monospace; font-size: 12px;"
        )
        layout.addWidget(self.log_view, stretch=1)
