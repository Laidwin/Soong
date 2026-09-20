"""Tests of the YouTube metadata cleaning and of the text normalisation."""

from __future__ import annotations

import pytest

from soong.utils.text_utils import (
    clean_artist_name,
    clean_youtube_title,
    normalized_tokens,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Vital (Clip Officiel)", "Vital"),
        ("Danger [Official Music Video]", "Danger"),
        ("EL CHAPO (Official Video) | HD", "EL CHAPO"),
        ("LONELY - Official Audio", "LONELY"),
        ("Sucrée (Prod. by Someone)", "Sucrée"),
        ("Formidable (Lyrics Video) 4K", "Formidable"),
        ("Number (Visualizer)", "Number"),
        ("Minuit", "Minuit"),  # nothing to remove
    ],
)
def test_clean_youtube_title(raw, expected):
    assert clean_youtube_title(raw) == expected


def test_clean_youtube_title_keeps_a_meaningful_parenthetical():
    assert clean_youtube_title("Nouveau Départ (Pt. 2)") == "Nouveau Départ (Pt. 2)"


def test_clean_artist_name():
    assert clean_artist_name("SomeArtistVEVO") == "SomeArtist"
    assert clean_artist_name("Le Keur - Topic") == "Le Keur"
    assert clean_artist_name("Le Keur Official") == "Le Keur"


def test_normalized_tokens_strips_accents_and_punctuation():
    assert normalized_tokens("Sucrée, Pt.2!") == ["sucree", "pt", "2"]
