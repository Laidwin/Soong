"""Desktop implementation of `ReviewProvider`, with a thread safe handoff.

The pipeline runs inside a `PipelineWorker` (a QThread). When it reaches the
review step it calls `request_review()` FROM that worker thread, and the call
has to block until a human validates the text. Since Qt forbids touching
widgets outside the main thread, the handoff works like this:

1. `request_review`, on the worker thread, emits the `review_requested` signal
   and blocks on a `queue.Queue().get()`.
2. The main thread shows the review screen, and on the validation click calls
   `submit_review(text)`, which pushes the text into the queue.
3. The queue releases the worker thread, which receives the validated text.
"""

from __future__ import annotations

import queue
from abc import ABCMeta

from PySide6.QtCore import QObject, Signal

from ..review_provider import ReviewProvider


class _QtABCMeta(type(QObject), ABCMeta):
    """Metaclass combining the QObject (Shiboken) metaclass with ABCMeta.

    Without it, inheriting from both `QObject` and the `ReviewProvider` abstract
    base class raises a metaclass conflict.
    """


class GuiReviewProvider(QObject, ReviewProvider, metaclass=_QtABCMeta):
    """`ReviewProvider` delegating validation to the UI through signals."""

    review_requested = Signal(str, str)

    def __init__(self) -> None:
        super().__init__()
        self._response_queue: "queue.Queue[str]" = queue.Queue(maxsize=1)

    def request_review(self, raw_text: str, track_id: str) -> str:
        """Called on the worker thread: blocks until `submit_review` is called."""
        self.review_requested.emit(raw_text, track_id)
        return self._response_queue.get()

    def submit_review(self, validated_text: str) -> None:
        """Called on the UI thread on the validation click: releases the worker."""
        self._response_queue.put(validated_text)
