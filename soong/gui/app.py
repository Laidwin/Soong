"""Entry point of the desktop application: QApplication, theme and main window."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from ..config import Config
from .main_window import MainWindow

_DARK_STYLESHEET = """
QWidget { background-color: #1e1f22; color: #e6e6e6; font-size: 14px; }
QLineEdit, QPlainTextEdit, QTextEdit, QListWidget {
    background-color: #2b2d31; border: 1px solid #3a3d42; border-radius: 6px;
    padding: 6px; selection-background-color: #4a5b8c;
}
QPushButton {
    background-color: #4a5b8c; border: none; border-radius: 6px; padding: 8px 14px;
}
QPushButton:hover { background-color: #5a6ea8; }
QPushButton:disabled { background-color: #3a3d42; color: #888; }
QProgressBar {
    background-color: #2b2d31; border: 1px solid #3a3d42; border-radius: 6px;
    text-align: center; height: 20px;
}
QProgressBar::chunk { background-color: #4a5b8c; border-radius: 6px; }
QFrame { border: 1px solid #3a3d42; border-radius: 6px; }
"""


def run(config: Config | None = None) -> int:
    """Start the desktop application and return the Qt exit code."""
    config = config or Config.load()
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(config.gui.get("window_title", "Soong Lyrics Studio"))
    if config.gui.get("theme", "dark") == "dark":
        app.setStyleSheet(_DARK_STYLESHEET)

    window = MainWindow(config)
    window.show()
    return app.exec()
