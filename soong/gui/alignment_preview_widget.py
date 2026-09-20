"""Post alignment review screen: check the timing by ear before rendering.

Once forced alignment is done, and before the long ffmpeg render starts, this
screen lists the verses with their real timestamps. Clicking a verse seeks the
audio player to its start and plays, which confirms that the timing holds. The
render can then be started, or the alignment attempted again.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..forced_aligner import AlignedLine


def _format_seconds(seconds: float) -> str:
    total = int(max(seconds, 0.0))
    return f"{total // 60}:{total % 60:02d}"


class AlignmentPreviewWidget(QWidget):
    """Aligned verses, targeted playback and render confirmation."""

    render_confirmed = Signal(object)
    realign_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._lines: list[AlignedLine] = []
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)
        self._build_ui()

    @property
    def lines(self) -> list[AlignedLine]:
        """The aligned verses currently displayed."""
        return self._lines

    def load(self, lines: list[AlignedLine], audio_path: Path | None) -> None:
        """Show the aligned verses and load the audio to check them against."""
        self._lines = lines
        self.list_widget.clear()
        for line in lines:
            item = QListWidgetItem(
                f"[{_format_seconds(line.start)} - {_format_seconds(line.end)}]  {line.text}"
            )
            item.setData(Qt.ItemDataRole.UserRole, line.start)
            self.list_widget.addItem(item)
        if audio_path is not None and Path(audio_path).exists():
            self._player.setSource(Path(audio_path).absolute().as_uri())

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("Check the alignment")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        hint = QLabel(
            "Click a verse to hear it at its timestamp. If the timing is right, "
            "start the render; otherwise align again."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget, stretch=1)

        buttons = QHBoxLayout()
        self.realign_button = QPushButton("Align again")
        self.realign_button.clicked.connect(self._on_realign)
        buttons.addWidget(self.realign_button)
        buttons.addStretch(1)
        self.render_button = QPushButton("Start the render")
        self.render_button.setFixedWidth(160)
        self.render_button.clicked.connect(self._on_render)
        buttons.addWidget(self.render_button)
        layout.addLayout(buttons)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        start = float(item.data(Qt.ItemDataRole.UserRole) or 0.0)
        self._player.setPosition(int(start * 1000))
        self._player.play()

    def _on_render(self) -> None:
        self._player.stop()
        self.render_confirmed.emit(self._lines)

    def _on_realign(self) -> None:
        self._player.stop()
        self.realign_requested.emit()
