# Soong Lyrics Studio

Turn a music video URL into a **blurred video with the lyrics burned into the
pixels**, synchronised through **forced alignment** between the audio and the
text.

- **Text**: [Genius](https://genius.com) first, as it is the most reliable
  source, with local transcription as a fallback.
- **Timing**: always from `ctc-forced-aligner` (MMS model). Never from the
  transcription timestamps, which are not usable, and never from Genius.
- **Human validation**: mandatory whenever the text comes from the
  transcription fallback, through a dedicated screen in the desktop app or
  through a review file on the command line.
- **Two front ends**: a PySide6 desktop application, or a scriptable CLI.

Documentation: **<https://Laidwin.github.io/Soong/>**, built from
[`docs/`](./docs/index.md) with MkDocs.

- Getting started:
  [installation](./docs/installation.md),
  [desktop app](./docs/desktop-app.md),
  [command line](./docs/cli.md),
  [library](./docs/library.md)
- Reference:
  [configuration](./docs/configuration.md),
  [processing chain](./docs/processing-chain.md),
  [output format](./docs/output.md)
- Internals:
  [architecture](./docs/architecture.md),
  [packaging](./docs/packaging.md),
  [troubleshooting](./docs/troubleshooting.md),
  [contributing](./docs/contributing.md)

## Architecture

```text
soong/                  core, with no Qt dependency
├── downloader.py        yt-dlp: video file plus a 16 kHz mono WAV
├── genius_client.py     Genius lookup and match scoring
├── transcriber.py       fallback text from a local Lyricsmith checkout
├── lyrics_source.py     picks between Genius and the fallback
├── review_provider.py   human validation abstraction (file or desktop UI)
├── forced_aligner.py    MMS forced alignment into timestamped words and verses
├── subtitle_builder.py  verses and words turned into drawtext cues
├── renderer.py          ffmpeg: gblur plus drawtext, single pass, parsed progress
├── pipeline.py          event driven orchestrator
├── events.py            PipelineEvent, PipelineStep, StepStatus
├── config.py            config.yaml loading
├── gui/                 PySide6, the ONLY place that imports Qt
└── utils/               ffmpeg_utils, text_utils, logger
```

The core knows only the `ReviewProvider` and `PipelineEvent` abstractions, so
the desktop app and the CLI plug into it without coupling the business logic to
any presentation layer.

## Requirements

- Python 3.13 (an NVIDIA GPU with CUDA 12.4 is strongly recommended; the
  alignment falls back to the CPU when CUDA is unavailable).
- `ffmpeg` and `ffprobe` on the `PATH`. They are not bundled, as they weigh
  several gigabytes.
- A font file in `assets/fonts/`. None is shipped with the repository: download
  one, for instance [Montserrat](https://fonts.google.com/specimen/Montserrat),
  and point `subtitles.font_path` in `config.yaml` at it.
- A [Genius API token](https://genius.com/api-clients) for the preferred text
  source. Without it, every track goes through the transcription fallback.
- Optional: a local checkout of [**Lyricsmith**](https://github.com/Laidwin/Lyricsmith), the separate transcription
  project this pipeline uses as its fallback text source, with
  `lyricsmith.project_dir` in `config.yaml` pointing at it. Without it, tracks
  that Genius does not know cannot be processed.

## Installation

The environment is fully managed by [`uv`](https://docs.astral.sh/uv/) through
`pyproject.toml`. A single command creates `.venv`, installs Python 3.13 when
needed, and resolves every dependency, including torch from the CUDA index and
`ctc-forced-aligner` from git:

```bash
uv sync
```

Nothing else is needed on the Python side: no manual `venv`, no `pip install`.
Every command then runs through `uv run`, which keeps the environment in sync.

Copy `.env.example` to `.env` and fill in `GENIUS_ACCESS_TOKEN`.

> `requirements.txt` is kept as a readable mirror of the dependencies;
> `pyproject.toml` is the source of truth. Regenerate it with
> `uv export --no-hashes -o requirements.txt`.

## Usage

### Desktop application

```bash
uv run python gui_main.py
```

Paste the URL, follow the progress in real time, validate the lyrics while
listening to the track when the fallback was used, check the alignment by ear,
then render.

### Command line

```bash
uv run python main.py process "https://youtube.com/watch?v=..." --quality best --mode word
```

When a human validation is required, `outputs/review/<track>.review.txt` is
written. Correct it, replace its first line with `# VALIDATED`, then run the
same command again.

## Configuration

Everything lives in [`config.yaml`](./config.yaml): download format, Genius
match threshold, Lyricsmith checkout, alignment language and device, subtitle
style (font, size, outline, position, fade), gaussian blur, encoder settings and
the theme of the desktop app.

## Tests

```bash
uv run pytest -q
```

The tests cover the pure logic: review providers including the thread safe
handoff, aligner grouping and fallbacks, subtitle building, the ffmpeg
filtergraph, Genius scoring and metadata parsing. They need neither a GPU, nor
ffmpeg, nor torch: the heavy dependencies are imported lazily and stubbed.

## Packaging an executable

```bash
uv run pyinstaller build_exe.spec
```

Points to keep in mind:

- **Model checkpoints** and **ffmpeg.exe** are not bundled: they must sit next
  to the executable, and their absence is reported at startup rather than
  failing silently.
- CUDA builds of `torch` and `torchaudio` make the output much bigger, which is
  expected.
- Test the executable on a machine without Python, since DLL errors are common
  with PyInstaller and CUDA.

## Licence

[MIT](./LICENSE). The fonts and models used at runtime keep their own licences.
