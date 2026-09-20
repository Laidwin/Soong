"""Tests of the review providers: the file mode and the thread safe UI handoff."""

from __future__ import annotations

import threading
import time

import pytest

from soong.review_provider import (
    VALIDATION_MARKER,
    FileReviewProvider,
    PendingReviewError,
)


def test_file_review_blocks_then_accepts_the_validated_text(config):
    provider = FileReviewProvider(config)

    # First pass: the file does not exist yet, so it is created and we block.
    with pytest.raises(PendingReviewError) as raised:
        provider.request_review("verse one\nverse two", "track-1")
    review_path = raised.value.review_path
    assert review_path.exists()

    # The user validates: marker on the first line, corrected text below.
    review_path.write_text(
        f"{VALIDATION_MARKER}\nverse one\nverse two corrected", encoding="utf-8"
    )
    assert provider.request_review("ignored", "track-1") == "verse one\nverse two corrected"


def test_file_review_non_blocking_returns_the_raw_text(config):
    config.review["blocking"] = False
    provider = FileReviewProvider(config)

    assert provider.request_review("raw", "track-2") == "raw"


def test_gui_review_provider_thread_handoff():
    """`request_review` on a worker thread unblocks on `submit_review`."""
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from soong.gui.gui_review_provider import GuiReviewProvider

    # A QApplication must exist before any QObject is created.
    _app = QApplication.instance() or QApplication([])
    provider = GuiReviewProvider()
    result: dict[str, str] = {}

    def worker() -> None:
        result["text"] = provider.request_review("raw", "track-3")

    thread = threading.Thread(target=worker)
    thread.start()
    time.sleep(0.1)  # let the worker reach the blocking get()
    assert thread.is_alive()  # still blocked: nothing was submitted yet

    provider.submit_review("validated text")
    thread.join(timeout=2.0)
    assert not thread.is_alive()  # released, no deadlock
    assert result["text"] == "validated text"
