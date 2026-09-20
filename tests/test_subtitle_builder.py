"""Tests of the subtitle builder, in both line and word modes."""

from __future__ import annotations

from soong.forced_aligner import AlignedLine, AlignedWord
from soong.subtitle_builder import SubtitleBuilder


def _line(text, start, end, words):
    return AlignedLine(
        text=text,
        start=start,
        end=end,
        words=[AlignedWord(word, word_start, word_end) for word, word_start, word_end in words],
    )


def test_line_mode_builds_one_cue_per_line(config):
    config.subtitles["mode"] = "line"
    lines = [
        _line("hello", 0.0, 1.0, [("hello", 0.0, 1.0)]),
        _line("goodbye now", 1.0, 2.5, [("goodbye", 1.0, 1.5), ("now", 1.5, 2.5)]),
    ]

    cues = SubtitleBuilder(config).build(lines)

    assert [cue.text for cue in cues] == ["hello", "goodbye now"]


def test_word_mode_builds_one_cue_per_word(config):
    config.subtitles["mode"] = "word"
    lines = [_line("goodbye now", 1.0, 2.5, [("goodbye", 1.0, 1.5), ("now", 1.5, 2.5)])]

    cues = SubtitleBuilder(config).build(lines)

    assert [cue.text for cue in cues] == ["goodbye", "now"]


def test_minimum_cue_duration_is_enforced(config):
    config.subtitles["mode"] = "line"
    builder = SubtitleBuilder(config)
    lines = [_line("flash", 0.0, 0.05, [("flash", 0.0, 0.05)])]

    cues = builder.build(lines)

    assert cues[0].end - cues[0].start >= builder.min_cue_duration - 1e-9


def test_cues_are_sorted_by_start_time(config):
    lines = [
        _line("second", 5.0, 6.0, [("second", 5.0, 6.0)]),
        _line("first", 1.0, 2.0, [("first", 1.0, 2.0)]),
    ]

    cues = SubtitleBuilder(config).build(lines)

    assert [cue.text for cue in cues] == ["first", "second"]
