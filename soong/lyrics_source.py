"""Lyrics TEXT retrieval: Genius first, local transcription as a fallback.

Timing never originates here, neither from Genius nor from the transcription
segments. This module only yields text plus the provenance of that text, which
decides whether a human review is mandatory.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .config import Config
from .events import PipelineEvent, PipelineStep, StepStatus
from .genius_client import GeniusClient
from .transcriber import LyricsmithTranscriber, Transcriber
from .utils.logger import get_logger
from .utils.text_utils import slugify

logger = get_logger("lyrics_source")

EventCallback = Callable[[PipelineEvent], None]

SOURCE_GENIUS = "genius"
SOURCE_TRANSCRIPTION = "transcription_fallback"


class LyricsSourceError(RuntimeError):
    """No lyrics source was able to provide any text."""


@dataclass
class LyricsResult:
    """Lyrics text together with its provenance.

    Attributes:
        text: Cleaned raw lyrics, one verse per line.
        source: `SOURCE_GENIUS` or `SOURCE_TRANSCRIPTION`.
        track_id: Filesystem safe identifier derived from "artist - title".
        match_score: Genius match score between 0 and 1, `None` for the fallback.
        needs_review: True when a human validation is mandatory.
    """

    text: str
    source: str
    track_id: str
    match_score: float | None = None
    needs_review: bool = False


def _emit(
    cb: EventCallback | None, status: StepStatus, message: str = "", **kw: Any
) -> None:
    if cb is not None:
        cb(PipelineEvent(PipelineStep.LYRICS_FETCH, status, message, **kw))


class LyricsSource:
    """Pick the lyrics text, preferring Genius over local transcription."""

    def __init__(
        self,
        config: Config,
        *,
        genius_client: GeniusClient | None = None,
        transcriber: Transcriber | None = None,
    ) -> None:
        self.genius_client = genius_client or GeniusClient(config)
        self.transcriber = transcriber or LyricsmithTranscriber(config)

    def fetch(
        self,
        title: str,
        artist: str,
        audio_path: Path,
        on_event: EventCallback | None = None,
    ) -> LyricsResult:
        """Return the lyrics text of a track and where it came from."""
        track_id = slugify(f"{artist}-{title}")
        _emit(on_event, StepStatus.STARTED, f"Looking up lyrics for {artist} - {title}")

        match = self.genius_client.search(title, artist)
        if match is not None:
            _emit(
                on_event,
                StepStatus.COMPLETED,
                f"Lyrics from Genius (score {match.score:.2f})",
            )
            return LyricsResult(
                text=match.text,
                source=SOURCE_GENIUS,
                track_id=track_id,
                match_score=match.score,
                needs_review=False,
            )

        _emit(on_event, StepStatus.PROGRESS, "No Genius match: transcribing locally.")
        text = self.transcriber.transcribe(audio_path)
        if not text.strip():
            _emit(on_event, StepStatus.FAILED, "Empty transcription.")
            raise LyricsSourceError(f"No lyrics could be found for {artist} - {title}.")

        _emit(
            on_event,
            StepStatus.COMPLETED,
            "Transcription ready, human validation required.",
            payload={"raw_text": text, "track_id": track_id},
        )
        return LyricsResult(
            text=text,
            source=SOURCE_TRANSCRIPTION,
            track_id=track_id,
            match_score=None,
            needs_review=True,
        )
