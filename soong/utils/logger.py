"""Structured logging, with an extra handler the desktop UI can plug into.

The pipeline core never imports Qt. To surface logs in the UI without
duplicating the logging setup, this module exposes `attach_callback_handler`:
the UI plugs a thread safe callback into it and re-emits each record as a Qt
signal. On the command line, `rich` takes care of the display.
"""

from __future__ import annotations

import logging
from typing import Callable

_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"

try:
    from rich.logging import RichHandler

    _CONSOLE_HANDLER: logging.Handler = RichHandler(
        rich_tracebacks=True, show_path=False
    )
except ImportError:
    _CONSOLE_HANDLER = logging.StreamHandler()
    _CONSOLE_HANDLER.setFormatter(logging.Formatter(_LOG_FORMAT))

_ROOT_NAME = "soong"
_LYRICSMITH_ROOT_NAME = "pipeline"

_configured = False


def _configure_root() -> None:
    global _configured
    if _configured:
        return
    root = logging.getLogger(_ROOT_NAME)
    root.setLevel(logging.INFO)
    root.addHandler(_CONSOLE_HANDLER)
    root.propagate = False
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a child of the project root logger."""
    _configure_root()
    return logging.getLogger(f"{_ROOT_NAME}.{name}")


class CallbackLogHandler(logging.Handler):
    """Handler forwarding every formatted record to a callback."""

    def __init__(self, callback: Callable[[str], None], level: int = logging.INFO):
        super().__init__(level=level)
        self._callback = callback
        self.setFormatter(logging.Formatter(_LOG_FORMAT))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._callback(self.format(record))
        except Exception:
            self.handleError(record)


def attach_callback_handler(
    callback: Callable[[str], None], *, level: int = logging.INFO
) -> CallbackLogHandler:
    """Attach a `CallbackLogHandler` to this project and to Lyricsmith loggers.

    Returns the handler so that it can be removed later with `detach_handler`.
    """
    _configure_root()
    handler = CallbackLogHandler(callback, level=level)
    for logger_name in (_ROOT_NAME, _LYRICSMITH_ROOT_NAME):
        logger = logging.getLogger(logger_name)
        logger.addHandler(handler)
        if logger.level == logging.NOTSET or logger.level > level:
            logger.setLevel(level)
    return handler


def detach_handler(handler: logging.Handler) -> None:
    """Remove a handler previously attached by `attach_callback_handler`."""
    for logger_name in (_ROOT_NAME, _LYRICSMITH_ROOT_NAME):
        logging.getLogger(logger_name).removeHandler(handler)
