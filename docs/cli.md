# Command line

```bash
uv run python main.py process "https://youtube.com/watch?v=..."
```

The command line does the same work as the desktop app, unattended. It is the
mode for batch processing and for machines with no display. The only difference
is the human review, which happens through a file instead of a screen.

## `process`

```bash
uv run python main.py process "<url>" --quality best --mode word
```

| Argument | Type | Default | Notes |
| --- | --- | --- | --- |
| `url` | str | required | Anything yt-dlp accepts |
| `--quality` | `fast`, `balanced`, `best` | from `config.yaml` | Overrides `lyricsmith.quality_preset` for this run |
| `--mode` | `line`, `word` | from `config.yaml` | Overrides `subtitles.mode` for this run |
| `--config` | path | `config.yaml` at the project root | Uses an alternative configuration file |

`--quality` only matters when the run falls back to transcription, since it is
the Demucs preset Lyricsmith uses.

## `gui`

```bash
uv run python main.py gui
```

Starts the desktop app, exactly like `python gui_main.py`. It exists so that a
single entry point covers both modes.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | The video was rendered, its path is printed |
| 1 | The run failed, the reason is printed |
| 2 | A human review is pending |

Exit code 2 is not an error. It means the lyrics came from transcription and
nobody has validated them yet.

## The review cycle

When a review is pending, the run stops after writing a file:

```text
outputs/review/le-keur-vital.review.txt
```

```text
# Remove this help line, correct the lyrics below, then replace
# the WHOLE first line with exactly: # VALIDATED
first verse of the song
second verse of the song
```

Correct the lyrics, then replace the **whole first line** with exactly
`# VALIDATED`, including the `#`. Run the same command again: the file is read,
the validated text is used, and the run continues into the alignment.

The download is not repeated, since the files are already in
`outputs/downloads/`. The transcription is, unless Genius answers this time.

!!! warning "Turning the review off"
    `review.require_manual_review: false` or `review.blocking: false` renders
    the raw transcription unchecked. A transcription error propagates into the
    timing and then into the picture, so this is a trade for batch experiments,
    not a default worth keeping.

## Logging

Every pipeline event is logged as it happens:

```text
[DOWNLOAD/PROGRESS 46%] Downloading.
[LYRICS_FETCH/COMPLETED] Lyrics from Genius (score 0.96)
[FORCED_ALIGNMENT/PROGRESS 60%] Running CTC alignment.
[RENDER/PROGRESS 73%] Rendering.
```

`rich` formats the output when it is installed, which `uv sync` guarantees.
The same records also feed the desktop log view, through the same logger.
