"""Tests of the renderer: filtergraph building, quoting and encoder arguments."""

from __future__ import annotations

from soong.renderer import VideoRenderer, _quote
from soong.subtitle_builder import DrawTextCue


def test_quote_escapes_colon_and_backslash():
    # _quote only ever handles control values such as paths and expressions.
    # Apostrophes never reach it, because lyrics go through a text file.
    assert _quote("C:/Fonts/arial.ttf") == "'C\\:/Fonts/arial.ttf'"
    assert _quote("a\\b") == "'a\\\\b'"


def test_lyrics_go_to_a_text_file_not_into_the_filtergraph(config, tmp_path):
    # Lyrics with apostrophes or commas must not appear in the graph, which
    # they would corrupt; they are written to a file referenced by textfile=.
    renderer = VideoRenderer(config)
    cues = [DrawTextCue("j'ai vu l'amour, toi", 45.14, 48.3)]

    graph = renderer._build_filtergraph(cues, tmp_path)

    assert "j'ai" not in graph and "l'amour" not in graph
    assert "textfile=" in graph
    assert "between(t,45.14,48.3)" in graph
    written = list(tmp_path.glob("cue_*.txt"))
    assert len(written) == 1
    assert written[0].read_text(encoding="utf-8") == "j'ai vu l'amour, toi"


def test_filtergraph_starts_with_blur_and_ends_with_output(config, tmp_path):
    renderer = VideoRenderer(config)

    graph = renderer._build_filtergraph([DrawTextCue("hello", 0.0, 1.0)], tmp_path)

    assert graph.startswith("[0:v]gblur=sigma=")
    assert graph.endswith("[v]")
    assert "drawtext=" in graph


def test_drawtext_contains_timing_and_position(config, tmp_path):
    renderer = VideoRenderer(config)

    filter_string = renderer._drawtext(DrawTextCue("hello, you", 1.5, 3.0), tmp_path / "c.txt")

    assert "between(t,1.5,3.0)" in filter_string
    assert "x=(w-text_w)/2" in filter_string
    assert "textfile=" in filter_string


def test_word_mode_builds_one_drawtext_per_cue(config, tmp_path):
    renderer = VideoRenderer(config)
    cues = [DrawTextCue("a", 0.0, 1.0), DrawTextCue("b", 1.0, 2.0)]

    assert renderer._build_filtergraph(cues, tmp_path).count("drawtext=") == 2


def test_encoder_args_libx264(config):
    config.video["codec"] = "libx264"
    config.video["crf"] = 20
    config.video["preset"] = "fast"

    args = VideoRenderer(config)._encoder_args()

    assert args == ["-c:v", "libx264", "-crf", "20", "-preset", "fast"]


def test_encoder_args_nvenc_uses_cq(config):
    config.video["codec"] = "h264_nvenc"
    config.video["crf"] = 19
    config.video["preset"] = "p5"

    args = VideoRenderer(config)._encoder_args()

    assert args[:2] == ["-c:v", "h264_nvenc"]
    assert "-cq" in args and "19" in args
    assert "-crf" not in args  # nvenc has no -crf


def test_encoder_args_nvenc_falls_back_on_an_x264_preset(config):
    config.video["codec"] = "h264_nvenc"
    config.video["preset"] = "veryslow"  # not a valid nvenc preset

    assert "p5" in VideoRenderer(config)._encoder_args()


def test_y_expression_follows_the_configured_position(config):
    config.subtitles["position"] = "top"
    assert VideoRenderer(config)._y_expression() == str(config.subtitles["margin_px"])

    config.subtitles["position"] = "center"
    assert VideoRenderer(config)._y_expression() == "(h-text_h)/2"

    config.subtitles["position"] = "bottom"
    assert VideoRenderer(config)._y_expression().startswith("h-text_h-")
