"""Human validation of the lyrics text, behind a single abstraction.

`pipeline.py` only ever knows `ReviewProvider`, never a concrete class. The
front end picks the implementation when it builds the pipeline:

- the command line injects `FileReviewProvider`: a file is written, a
  ``# VALIDATED`` marker is expected, and the command is run again;
- the desktop app injects `GuiReviewProvider`, defined in
  ``gui/gui_review_provider.py`` and deliberately not imported here, so that
  the core stays free of PySide6.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from .config import Config
from .utils.logger import get_logger

logger = get_logger("review")

VALIDATION_MARKER = "# VALIDATED"


class PendingReviewError(RuntimeError):
    """A human validation is required but has not been provided yet.

    In blocking file mode the user edits and validates the review file, then
    runs the same command again.
    """

    def __init__(self, review_path: Path):
        self.review_path = review_path
        super().__init__(
            f"Human validation required. Edit the file below, then replace its "
            f"first line with exactly '{VALIDATION_MARKER}':\n  {review_path}\n"
            f"Then run the same command again."
        )


class ReviewProvider(ABC):
    """Contract for the human validation of the lyrics text."""

    @abstractmethod
    def request_review(self, raw_text: str, track_id: str) -> str:
        """Block until a human validates the text, then return the final text.

        The implementation decides HOW the validation is obtained, through a
        file or through the desktop UI. The returned text may have been
        corrected by the reviewer.
        """


class FileReviewProvider(ReviewProvider):
    """Validation through a text file, used by the command line interface.

    Writes ``{review_dir}/{track_id}.review.txt`` prefilled with the raw text.
    When the file starts with the validation marker, the rest is returned as the
    validated lyrics. Otherwise a `PendingReviewError` is raised in blocking
    mode, or the raw text is returned as is when blocking is disabled.
    """

    def __init__(self, config: Config) -> None:
        self.review_dir = config.resolve_path(
            config.review.get("review_dir", "./outputs/review")
        )
        self.review_dir.mkdir(parents=True, exist_ok=True)
        self.blocking = bool(config.review.get("blocking", True))

    def request_review(self, raw_text: str, track_id: str) -> str:
        path = self._review_path(track_id)
        if path.exists():
            return self._read_existing(path, track_id)

        path.write_text(self._template(raw_text), encoding="utf-8")
        if self.blocking:
            raise PendingReviewError(path)
        return raw_text.strip()

    def _review_path(self, track_id: str) -> Path:
        return self.review_dir / f"{track_id}.review.txt"

    def _read_existing(self, path: Path, track_id: str) -> str:
        content = path.read_text(encoding="utf-8")
        first_line, _, remainder = content.partition("\n")
        if first_line.strip() == VALIDATION_MARKER:
            logger.info("Lyrics validated through %s", path.name)
            return remainder.strip()

        if self.blocking:
            raise PendingReviewError(path)
        logger.warning("Non blocking review: using the raw text for %s", track_id)
        return content.strip()

    @staticmethod
    def _template(raw_text: str) -> str:
        return (
            f"# Remove this help line, correct the lyrics below, then replace\n"
            f"# the WHOLE first line with exactly: {VALIDATION_MARKER}\n"
            f"{raw_text.strip()}\n"
        )
