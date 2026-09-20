# Installation

## What you need

| Requirement | Why | Optional |
| --- | --- | --- |
| Python 3.13 | The project pins `>=3.13,<3.14` | No, but `uv` installs it for you |
| `ffmpeg` and `ffprobe` on the `PATH` | Audio extraction, duration probing, the render | No |
| A font file in `assets/fonts/` | `drawtext` needs a real font file | No |
| A Genius API token | The preferred lyrics source | Yes, without it every track is transcribed |
| An NVIDIA GPU with CUDA 12.4 | Faster alignment and rendering | Yes, both fall back to the CPU |
| A Lyricsmith checkout | The transcription fallback | Yes, needed only for tracks Genius does not know |

## Install the environment

The environment is managed entirely by [uv](https://docs.astral.sh/uv/) from
`pyproject.toml`:

```bash
uv sync
```

That one command creates `.venv`, installs Python 3.13 when it is missing, and
resolves every dependency, including `torch` from the CUDA 12.4 index and
`ctc-forced-aligner` from git. There is no manual `venv` and no `pip install`.
Every command then runs through `uv run`, which keeps the environment in sync.

`requirements.txt` is kept as a readable mirror and is regenerated with
`uv export --no-hashes -o requirements.txt`.

## Install ffmpeg

ffmpeg and ffprobe are not bundled: they weigh several gigabytes and the
project would be a poor place to ship them from. Install them from your package
manager, or from [ffmpeg.org](https://ffmpeg.org/download.html) on Windows, and
make sure both are on the `PATH`. A missing one is reported before any work
starts, not halfway through a render.

## Add a font

No font ships with the repository, because fonts carry their own licences.
Download one, for instance
[Montserrat](https://fonts.google.com/specimen/Montserrat), and drop the file
in `assets/fonts/`. The default configuration expects `Montserrat-Bold.ttf`;
any `.ttf` or `.otf` works as long as `subtitles.font_path` points at it.

Font files are git ignored, so each clone provides its own.

## Set the Genius token

```bash
cp .env.example .env
```

```ini
GENIUS_ACCESS_TOKEN=your_token_here
```

Tokens are created at [genius.com/api-clients](https://genius.com/api-clients).
`.env` is git ignored and must never be committed. Without a token the Genius
step is skipped entirely and every track goes through transcription, which
costs a model run and a human review.

## Connect Lyricsmith, optionally

[Lyricsmith](https://github.com/Laidwin/Lyricsmith) is the separate project
that transcribes a song into lyrics. Soong uses it as its fallback text source.
It is not a pip package: clone it anywhere and point `config.yaml` at the
checkout.

```yaml
lyricsmith:
  project_dir: "./Lyricsmith"
```

The default is a `Lyricsmith` directory inside the project, which is git
ignored, so a checkout placed there needs no configuration at all. Without one,
tracks that Genius does not know fail with an explicit `TranscriptionError`.

## Check the installation

```bash
uv run pytest -q
```

The suite needs no GPU, no ffmpeg, no network and no model, so it passes on a
machine where only `uv sync` has been run. If it passes, the code is sound and
anything that still fails is an environment problem, which
[Troubleshooting](troubleshooting.md) covers.
