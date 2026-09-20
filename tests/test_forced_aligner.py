"""Tests of the verse grouping and the proportional fallbacks of the aligner.

The MMS model is never loaded: only the pure logic is exercised, from words
built by hand.
"""

from __future__ import annotations

from soong.forced_aligner import AlignedWord, ForcedAligner


def _words(spec: list[tuple[str, float, float]]) -> list[AlignedWord]:
    return [AlignedWord(text=text, start=start, end=end, score=1.0) for text, start, end in spec]


def test_group_into_lines_maps_words_to_verses(config):
    aligner = ForcedAligner(config)
    text = "hello there world\ngoodbye now"
    words = _words(
        [
            ("hello", 0.0, 0.5),
            ("there", 0.5, 0.8),
            ("world", 0.8, 1.5),
            ("goodbye", 2.0, 2.3),
            ("now", 2.3, 3.0),
        ]
    )
    lines = aligner.group_into_lines(words, text, total_duration=3.0)
    assert len(lines) == 2
    assert lines[0].text == "hello there world"
    assert lines[0].start == 0.0
    assert lines[0].end == 1.5
    assert lines[1].text == "goodbye now"
    assert lines[1].start == 2.0
    assert lines[1].end == 3.0


def test_group_into_lines_falls_back_when_words_missing(config):
    aligner = ForcedAligner(config)
    text = "a long line with quite a few words in it"
    # Too few aligned words, so the line is spread over the window instead.
    words = _words([("a", 0.0, 0.4)])
    lines = aligner.group_into_lines(words, text, total_duration=5.0)
    assert len(lines) == 1
    assert lines[0].end >= lines[0].start
    # Every word of the verse still gets time bounds.
    assert len(lines[0].words) == len(text.split())


def test_low_score_triggers_proportional(config):
    config.forced_alignment["low_score_threshold"] = 0.9  # force the fallback
    aligner = ForcedAligner(config)
    words = [
        AlignedWord("alpha", 0.0, 1.0, score=0.1),
        AlignedWord("beta", 1.0, 2.0, score=0.1),
    ]
    lines = aligner.group_into_lines(words, "alpha beta", total_duration=2.0)
    assert len(lines) == 1
    # Fallback: scores reset to zero, bounds spread by character count.
    assert all(word.score == 0.0 for word in lines[0].words)


def test_proportional_alignment_covers_duration():
    lines = ForcedAligner.proportional_alignment("a\nbb\ncccc", total_duration=7.0)
    assert len(lines) == 3
    assert lines[0].start == 0.0
    # Verses follow each other without a gap.
    for previous, following in zip(lines, lines[1:]):
        assert abs(previous.end - following.start) < 1e-6
