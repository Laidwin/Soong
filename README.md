<div align="center">

# Soong

**Turn a music video into a lyrics video.**

Paste a link. Soong finds the lyrics, syncs them to the voice word by word,
and renders a blurred video with the lyrics on screen.

[![Documentation](https://img.shields.io/badge/docs-laidwin.github.io%2FSoong-blue)](https://laidwin.github.io/Soong/)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)
[![Docs built with Kiln](https://img.shields.io/badge/docs%20built%20with-Kiln-f76b15)](https://github.com/Laidwin/kiln)

[**Documentation**](https://laidwin.github.io/Soong/) · [**Quick start**](#quick-start)

</div>

```text
[DOWNLOAD/COMPLETED] Downloaded: Le Keur - Vital
[LYRICS_FETCH/COMPLETED] Lyrics from Genius (score 0.96)
[REVIEW/COMPLETED] Reliable lyrics from Genius: no review needed.
[FORCED_ALIGNMENT/COMPLETED 100%] 42 verses aligned.
[SUBTITLE_BUILD/COMPLETED] 42 cues generated.
[RENDER/COMPLETED 100%] Video rendered: le-keur-vital.mp4
```

---

> **Part of a duo.** [Lyricsmith](https://github.com/Laidwin/Lyricsmith) turns a
> song into timestamped lyrics. **Soong** turns a music video into a lyrics
> video, and calls Lyricsmith when Genius does not know the song.
>
> ```text
> music video ──▶ lyrics (Genius, or Lyricsmith as a fallback) ──▶ word-level sync ──▶ lyrics video
> ```

---

## Highlights

- **Accurate timing.** Every word is aligned on the singer's voice with forced alignment, instead of relying on approximate timestamps.
- **Reliable lyrics.** Soong takes the text from [Genius](https://genius.com) first, and asks [Lyricsmith](https://github.com/Laidwin/Lyricsmith) to transcribe the song when Genius does not know it.
- **You stay in control.** When the lyrics come from a transcription, you review them while listening to the track before anything is rendered.
- **Desktop app or command line.** A PySide6 app for everyday use, a CLI for scripts and batches.
- **Your style.** Font, size, outline, position, fade, blur strength and line or word-by-word display are all set in one `config.yaml`.
- **Runs at home.** Designed for a single consumer GPU with 8 GB of memory, with a CPU fallback.

---

## Quick start

You need [uv](https://docs.astral.sh/uv/), `ffmpeg` on your `PATH`,
a [Genius API token](https://genius.com/api-clients) and a font file.
An NVIDIA GPU is strongly recommended.

```bash
git clone https://github.com/Laidwin/Soong.git
cd Soong
uv sync                     # installs Python 3.13 and every dependency
cp .env.example .env        # then add your GENIUS_ACCESS_TOKEN
```

Put a font in `assets/fonts/` (for instance [Montserrat](https://fonts.google.com/specimen/Montserrat))
and set `subtitles.font_path` in `config.yaml`.

**Desktop app:**

```bash
uv run python gui_main.py
```

**Command line:**

```bash
uv run python main.py process "https://youtube.com/watch?v=..." --mode word
```

To handle songs that Genius does not know, also set up [Lyricsmith](https://github.com/Laidwin/Lyricsmith)
and point `lyricsmith.project_dir` in `config.yaml` at it.

The [installation guide](https://laidwin.github.io/Soong/installation/) covers every detail,
and the [packaging guide](https://laidwin.github.io/Soong/packaging/) explains how to build a standalone executable.

---

## Documentation

| | |
| --- | --- |
| **Use it** | [Installation](https://laidwin.github.io/Soong/installation/) · [Desktop app](https://laidwin.github.io/Soong/desktop-app/) · [Command line](https://laidwin.github.io/Soong/cli/) · [Configuration](https://laidwin.github.io/Soong/configuration/) |
| **Understand it** | [Processing chain](https://laidwin.github.io/Soong/processing-chain/) · [Output format](https://laidwin.github.io/Soong/output/) · [Troubleshooting](https://laidwin.github.io/Soong/troubleshooting/) |
| **Build on it** | [Library](https://laidwin.github.io/Soong/library/) · [Architecture](https://laidwin.github.io/Soong/architecture/) · [Packaging](https://laidwin.github.io/Soong/packaging/) · [Contributing](https://laidwin.github.io/Soong/contributing/) |

Built with Python, PySide6, yt-dlp, PyTorch, ctc-forced-aligner and ffmpeg.
The test suite runs without a GPU, ffmpeg or PyTorch: `uv run pytest -q`.

---

## Responsible use

Soong is meant for personal use. Music videos and lyrics are protected by copyright:
respect the rights of artists and the terms of the platforms you download from,
and do not publish videos you do not have the rights to.

## License

[MIT](LICENSE). Fonts and models used at runtime keep their own licenses.
