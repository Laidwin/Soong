"""Main window: URL input, screen navigation and signal wiring."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..config import Config
from ..events import PipelineEvent, PipelineStep, StepStatus
from ..forced_aligner import AlignedLine
from ..utils.logger import attach_callback_handler, detach_handler
from .alignment_preview_widget import AlignmentPreviewWidget
from .gui_review_provider import GuiReviewProvider
from .pipeline_worker import PipelineWorker
from .progress_widget import ProgressWidget
from .review_widget import ReviewWidget


class MainWindow(QWidget):
    """Assemble the screens and drive the exchanges with the worker thread."""

    SCREEN_URL = 0
    SCREEN_PROGRESS = 1
    SCREEN_REVIEW = 2
    SCREEN_ALIGNMENT = 3
    SCREEN_FINAL = 4

    def __init__(self, config: Config) -> None:
        super().__init__()
        self.config = config
        self._worker: PipelineWorker | None = None
        self._review_provider: GuiReviewProvider | None = None
        self._audio_path: Path | None = None
        self._final_path: Path | None = None
        self._log_handler = None

        self.setWindowTitle(config.gui.get("window_title", "Soong Lyrics Studio"))
        self.resize(
            int(config.gui.get("window_width", 1000)),
            int(config.gui.get("window_height", 700)),
        )
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        self.stack = QStackedWidget()
        root.addWidget(self.stack)

        self.stack.addWidget(self._build_url_screen())

        self.progress_widget = ProgressWidget()
        self.stack.addWidget(self.progress_widget)

        self.review_widget = ReviewWidget()
        self.review_widget.validated.connect(self._on_review_validated)
        self.stack.addWidget(self.review_widget)

        self.alignment_widget = AlignmentPreviewWidget()
        self.alignment_widget.render_confirmed.connect(self._on_render_confirmed)
        self.alignment_widget.realign_requested.connect(self._on_realign_requested)
        self.stack.addWidget(self.alignment_widget)

        self.stack.addWidget(self._build_final_screen())
        self.stack.setCurrentIndex(self.SCREEN_URL)

    def _build_url_screen(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addStretch(1)

        title = QLabel("Soong Lyrics Studio")
        title.setStyleSheet("font-size: 28px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Paste a YouTube URL to build a blurred lyrics video.")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        row = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://www.youtube.com/watch?v=")
        self.url_input.returnPressed.connect(self._on_start)
        row.addWidget(self.url_input, stretch=1)
        self.start_button = QPushButton("Start")
        self.start_button.setFixedWidth(120)
        self.start_button.clicked.connect(self._on_start)
        row.addWidget(self.start_button)
        layout.addLayout(row)

        layout.addStretch(2)
        return widget

    def _build_final_screen(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addStretch(1)

        self.final_label = QLabel("Video rendered.")
        self.final_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.final_label.setWordWrap(True)
        self.final_label.setStyleSheet("font-size: 16px;")
        layout.addWidget(self.final_label)

        row = QHBoxLayout()
        row.addStretch(1)
        self.open_folder_button = QPushButton("Open the folder")
        self.open_folder_button.clicked.connect(self._open_output_folder)
        row.addWidget(self.open_folder_button)
        self.new_video_button = QPushButton("New video")
        self.new_video_button.clicked.connect(
            lambda: self.stack.setCurrentIndex(self.SCREEN_URL)
        )
        row.addWidget(self.new_video_button)
        row.addStretch(1)
        layout.addLayout(row)

        layout.addStretch(2)
        return widget

    def _on_start(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Missing URL", "Enter a YouTube URL.")
            return

        self.start_button.setEnabled(False)
        self.progress_widget.reset()
        self.stack.setCurrentIndex(self.SCREEN_PROGRESS)

        if self._log_handler is None:
            self._log_handler = attach_callback_handler(self.progress_widget.append_log)

        self._review_provider = GuiReviewProvider()
        self._review_provider.review_requested.connect(self._on_review_requested)

        self._worker = PipelineWorker(url, self.config, self._review_provider)
        self._worker.event_received.connect(self._on_event)
        self._worker.alignment_ready.connect(self._on_alignment_ready)
        self._worker.finished_ok.connect(self._on_finished_ok)
        self._worker.finished_error.connect(self._on_finished_error)
        self._worker.start()

    def _on_event(self, event: PipelineEvent) -> None:
        self.progress_widget.on_event(event)
        if (
            event.step == PipelineStep.DOWNLOAD
            and event.status == StepStatus.COMPLETED
            and event.payload
        ):
            audio = event.payload.get("audio_path")
            if audio:
                self._audio_path = Path(audio)

    def _on_review_requested(self, raw_text: str, track_id: str) -> None:
        self.review_widget.load(raw_text, self._audio_path)
        self.stack.setCurrentIndex(self.SCREEN_REVIEW)

    def _on_review_validated(self, text: str) -> None:
        if self._review_provider is not None:
            self._review_provider.submit_review(text)
        self.stack.setCurrentIndex(self.SCREEN_PROGRESS)

    def _on_alignment_ready(self, lines: list[AlignedLine]) -> None:
        self.alignment_widget.load(lines, self._audio_path)
        self.stack.setCurrentIndex(self.SCREEN_ALIGNMENT)

    def _on_render_confirmed(self, lines: list[AlignedLine]) -> None:
        if self._worker is not None:
            self._worker.submit_alignment(lines)
        self.stack.setCurrentIndex(self.SCREEN_PROGRESS)

    def _on_realign_requested(self) -> None:
        if self._worker is not None:
            self._worker.submit_alignment(self.alignment_widget.lines)
        QMessageBox.information(
            self,
            "Align again",
            "Adjust forced_alignment.language or the quality preset in "
            "config.yaml, then start again from the home screen.",
        )
        self.stack.setCurrentIndex(self.SCREEN_URL)
        self.start_button.setEnabled(True)

    def _on_finished_ok(self, path: str) -> None:
        self._final_path = Path(path)
        self.final_label.setText(f"Video rendered:\n{path}")
        self.stack.setCurrentIndex(self.SCREEN_FINAL)
        self.start_button.setEnabled(True)

    def _on_finished_error(self, message: str) -> None:
        QMessageBox.critical(self, "Pipeline failed", message)
        self.stack.setCurrentIndex(self.SCREEN_URL)
        self.start_button.setEnabled(True)

    def _open_output_folder(self) -> None:
        folder = (
            self._final_path.parent
            if self._final_path is not None
            else self.config.resolve_path(
                self.config.video.get("output_dir", "./outputs/final")
            )
        )
        if sys.platform == "win32":
            subprocess.run(["explorer", str(folder)])
        elif sys.platform == "darwin":
            subprocess.run(["open", str(folder)])
        else:
            subprocess.run(["xdg-open", str(folder)])

    def closeEvent(self, event) -> None:
        """Detach the log handler when the window closes."""
        if self._log_handler is not None:
            detach_handler(self._log_handler)
            self._log_handler = None
        super().closeEvent(event)
