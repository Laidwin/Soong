"""Lyrics review screen, with the track playing alongside the editable text.

Shown only when the text comes from the transcription fallback, where a human
validation is mandatory. The user listens to the track while correcting the
text, one line per verse, then validates, which releases the worker thread and
starts the forced alignment.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)


def _format_ms(milliseconds: int) -> str:
    seconds = max(milliseconds, 0) // 1000
    return f"{seconds // 60}:{seconds % 60:02d}"


class ReviewWidget(QWidget):
    """Editable lyrics area, audio player and validation button."""

    validated = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)
        self._build_ui()
        self._connect_signals()

    def load(self, raw_text: str, audio_path: Path | None) -> None:
        """Prefill the text area and load the audio to listen to."""
        self.editor.setPlainText(raw_text.strip())
        if audio_path is not None and Path(audio_path).exists():
            self._player.setSource(Path(audio_path).absolute().as_uri())
        self._update_validate_enabled()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("Check the transcribed lyrics")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        hint = QLabel(
            "Correct the lyrics below, one line per verse, while listening to "
            "the track. Precise timings are computed after validation."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText("Lyrics")
        layout.addWidget(self.editor, stretch=1)

        controls = QHBoxLayout()
        self.play_button = QPushButton("Play")
        self.play_button.setFixedWidth(90)
        controls.addWidget(self.play_button)

        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 0)
        controls.addWidget(self.position_slider, stretch=1)

        self.time_label = QLabel("0:00 / 0:00")
        controls.addWidget(self.time_label)
        layout.addLayout(controls)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        self.validate_button = QPushButton("Validate")
        self.validate_button.setFixedWidth(140)
        bottom.addWidget(self.validate_button)
        layout.addLayout(bottom)

    def _connect_signals(self) -> None:
        self.play_button.clicked.connect(self._toggle_play)
        self.validate_button.clicked.connect(self._on_validate)
        self.editor.textChanged.connect(self._update_validate_enabled)

        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.playbackStateChanged.connect(self._on_playback_state_changed)
        self.position_slider.sliderMoved.connect(self._player.setPosition)

    def _toggle_play(self) -> None:
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def _on_playback_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.play_button.setText("Pause" if playing else "Play")

    def _on_position_changed(self, position: int) -> None:
        if not self.position_slider.isSliderDown():
            self.position_slider.setValue(position)
        self._refresh_time()

    def _on_duration_changed(self, duration: int) -> None:
        self.position_slider.setRange(0, duration)
        self._refresh_time()

    def _refresh_time(self) -> None:
        self.time_label.setText(
            f"{_format_ms(self._player.position())} / {_format_ms(self._player.duration())}"
        )

    def _update_validate_enabled(self) -> None:
        self.validate_button.setEnabled(bool(self.editor.toPlainText().strip()))

    def _on_validate(self) -> None:
        self._player.stop()
        self.validated.emit(self.editor.toPlainText().strip())
