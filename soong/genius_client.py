"""Lyrics lookup on Genius, the preferred (most reliable) text source.

Only the lyrics text is used. Genius does not provide timing, and the timing it
would imply is never trusted: timestamps always come from forced alignment.
"""

from __future__ import annotations

import difflib
import os
from dataclasses import dataclass
from typing import Any

from .config import Config
from .utils.logger import get_logger
from .utils.text_utils import normalized_tokens, strip_genius_artifacts

logger = get_logger("genius")

_TITLE_WEIGHT = 0.7
_ARTIST_WEIGHT = 0.3
_UNKNOWN_ARTIST_SCORE = 0.5


@dataclass
class GeniusMatch:
    """Lyrics found on Genius, with the confidence of the match."""

    text: str
    score: float


def match_score(title: str, artist: str, song: Any) -> float:
    """Score the similarity between a search query and a Genius result.

    Weighted average of the title and artist similarities.
    """
    got_title = str(getattr(song, "title", "") or "")
    got_artist = str(getattr(song, "artist", "") or "")
    title_score = _text_similarity(title, got_title)
    artist_score = (
        _text_similarity(artist, got_artist)
        if artist and got_artist
        else _UNKNOWN_ARTIST_SCORE
    )
    return round(_TITLE_WEIGHT * title_score + _ARTIST_WEIGHT * artist_score, 3)


def _text_similarity(left: str, right: str) -> float:
    """Lenient similarity between two labels, between 0 and 1.

    Combines a sequence ratio over normalised tokens with a containment score
    (share of the tokens of `left` present in `right`) and keeps the best of the
    two, so that an extra on the Genius side such as "(feat. X)" or "(Remix)"
    does not drag the score down.
    """
    left_tokens, right_tokens = normalized_tokens(left), normalized_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    sequence = difflib.SequenceMatcher(
        None, " ".join(left_tokens), " ".join(right_tokens)
    ).ratio()
    containment = len(set(left_tokens) & set(right_tokens)) / len(set(left_tokens))
    return max(sequence, containment)


class GeniusClient:
    """Thin wrapper around `lyricsgenius`, tolerant to every failure mode.

    Any problem (missing token, missing library, network error, weak match)
    results in `None` rather than an exception: the caller then falls back to
    local transcription.
    """

    def __init__(self, config: Config) -> None:
        genius = config.genius
        self.min_match_score = float(genius.get("min_match_score", 0.75))
        self.timeout = int(genius.get("timeout_seconds", 10))
        self.token_env = genius.get("access_token_env", "GENIUS_ACCESS_TOKEN")

    def search(self, title: str, artist: str) -> GeniusMatch | None:
        """Return the lyrics found for a track, or `None` when unusable."""
        song = self._search_song(title, artist)
        if song is None:
            return None

        score = match_score(title, artist, song)
        if score < self.min_match_score:
            logger.info(
                "Genius match scored %.2f, below the %.2f threshold: ignored.",
                score,
                self.min_match_score,
            )
            return None

        text = strip_genius_artifacts(song.lyrics)
        if not text.strip():
            return None
        return GeniusMatch(text=text, score=score)

    def _search_song(self, title: str, artist: str) -> Any | None:
        token = os.environ.get(self.token_env)
        if not token:
            logger.info("No Genius token in %s: skipping Genius.", self.token_env)
            return None

        try:
            import lyricsgenius
        except ImportError:
            logger.warning("lyricsgenius is not installed: skipping Genius.")
            return None

        try:
            client = lyricsgenius.Genius(
                token,
                timeout=self.timeout,
                retries=2,
                remove_section_headers=False,
            )
            if hasattr(client, "verbose"):
                client.verbose = False
            song = client.search_song(title=title, artist=artist)
        except Exception as exc:
            logger.warning("Genius search failed: %s", exc)
            return None

        if song is None or not getattr(song, "lyrics", ""):
            logger.info("Genius returned no usable result.")
            return None
        return song
