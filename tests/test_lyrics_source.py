"""Tests of `LyricsSource`: Genius first, transcription fallback afterwards."""

from __future__ import annotations

from pathlib import Path

import pytest

from soong.genius_client import GeniusMatch
from soong.lyrics_source import (
    SOURCE_GENIUS,
    SOURCE_TRANSCRIPTION,
    LyricsSource,
    LyricsSourceError,
)


class _StubGenius:
    """Genius client returning a fixed answer, without any network call."""

    def __init__(self, match: GeniusMatch | None) -> None:
        self.match = match

    def search(self, title: str, artist: str) -> GeniusMatch | None:
        return self.match


class _StubTranscriber:
    """Transcriber returning a fixed text, without loading any model."""

    def __init__(self, text: str) -> None:
        self.text = text

    def transcribe(self, audio_path: Path) -> str:
        return self.text


def _source(config, *, match=None, transcription="") -> LyricsSource:
    return LyricsSource(
        config,
        genius_client=_StubGenius(match),
        transcriber=_StubTranscriber(transcription),
    )


def test_fetch_prefers_genius_and_skips_review(config):
    source = _source(config, match=GeniusMatch(text="verse one\nverse two", score=0.91))

    result = source.fetch("Title", "Artist", Path("fake.wav"))

    assert result.source == SOURCE_GENIUS
    assert result.match_score == 0.91
    assert result.needs_review is False
    assert result.text == "verse one\nverse two"


def test_fetch_falls_back_to_transcription_and_requires_review(config):
    source = _source(config, match=None, transcription="verse one\nverse two")

    result = source.fetch("Title", "Artist", Path("fake.wav"))

    assert result.source == SOURCE_TRANSCRIPTION
    assert result.match_score is None
    assert result.needs_review is True
    assert result.text == "verse one\nverse two"
    assert result.track_id  # a non empty slug


def test_fetch_raises_when_every_source_is_empty(config):
    source = _source(config, match=None, transcription="   \n  ")

    with pytest.raises(LyricsSourceError):
        source.fetch("Title", "Artist", Path("fake.wav"))


def test_track_id_is_filesystem_safe(config):
    source = _source(config, match=GeniusMatch(text="text", score=1.0))

    result = source.fetch("Sucrée, Pt. 2", "Le Keur", Path("fake.wav"))

    assert result.track_id == "le-keur-sucree-pt-2"
