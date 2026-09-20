"""Tests of the title and artist parsing of the download metadata."""

from __future__ import annotations

from soong.downloader import _split_title_artist


def test_split_uses_track_and_artist_metadata():
    info = {"track": "Vital", "artist": "Le Keur", "title": "does not matter"}
    assert _split_title_artist(info) == ("Vital", "Le Keur")


def test_split_parses_dash_title_and_strips_promo():
    info = {"title": "Le Keur - Vital (Clip Officiel)"}
    title, artist = _split_title_artist(info)
    assert title == "Vital"  # "(Clip Officiel)" removed
    assert artist == "Le Keur"


def test_split_strips_pipe_and_trailing_noise():
    info = {"title": "Le Keur - Danger | Official Music Video"}
    title, artist = _split_title_artist(info)
    assert title == "Danger"
    assert artist == "Le Keur"


def test_split_cleans_vevo_and_topic_uploader():
    info = {"title": "Just A Title", "uploader": "SomeArtistVEVO"}
    title, artist = _split_title_artist(info)
    assert title == "Just A Title"
    assert artist == "SomeArtist"

    topic_info = {"title": "Another", "uploader": "Le Keur - Topic"}
    _, topic_artist = _split_title_artist(topic_info)
    assert topic_artist == "Le Keur"
