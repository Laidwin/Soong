"""Tests of the Genius match scoring and of the lyrics page cleaning."""

from __future__ import annotations

from types import SimpleNamespace

from soong.genius_client import match_score
from soong.utils.text_utils import strip_genius_artifacts


def test_match_score_high_on_exact_result():
    song = SimpleNamespace(title="Vital", artist="Le Keur")
    assert match_score("Vital", "Le Keur", song) > 0.95


def test_match_score_low_on_mismatch():
    song = SimpleNamespace(title="Completely Different", artist="Someone Else")
    assert match_score("Vital", "Le Keur", song) < 0.5


def test_match_score_tolerant_to_feat_and_accents():
    # The Genius title adds a "(feat. ...)" and drops an accent: still a match.
    song = SimpleNamespace(title="Sucree (feat. Someone)", artist="Le Keur")
    assert match_score("Sucrée", "Le Keur", song) >= 0.9


def test_strip_genius_artifacts_removes_sections_and_header():
    raw = (
        "12 ContributorsVital Lyrics\n[Couplet 1]\nfirst sung line\n"
        "[Refrain]\nsecond sung line3Embed"
    )
    cleaned = strip_genius_artifacts(raw)
    assert "[Couplet 1]" not in cleaned
    assert "[Refrain]" not in cleaned
    assert "Embed" not in cleaned
    assert "first sung line" in cleaned
    assert "second sung line" in cleaned
