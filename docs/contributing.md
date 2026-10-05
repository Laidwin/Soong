---
title: Contributing
---

## Running the tests

```bash
uv run pytest -q
```

43 tests, well under a second, with no GPU, no ffmpeg, no network and no model.

| File | What it protects |
| --- | --- |
| `test_downloader.py` | Title and artist parsing, promotional noise removal |
| `test_genius_client.py` | Match scoring, tolerance to `(feat. ...)` and accents, page cleaning |
| `test_lyrics_source.py` | Source selection, the review flag, the empty source error, the track id |
| `test_forced_aligner.py` | Verse grouping, the low score and missing word fallbacks, proportional alignment |
| `test_subtitle_builder.py` | Line and word modes, the minimum duration, cue ordering |
| `test_renderer.py` | Filtergraph structure, quoting, lyrics kept out of the graph, encoder arguments |
| `test_review_provider.py` | The file review cycle, the thread handoff, the absence of a deadlock |

The `config` fixture loads the real `config.yaml` and redirects every output
directory into `tmp_path`, so the tests exercise the shipped defaults without
writing anywhere else.

## Conventions

**The core never imports Qt.** Anything importing PySide6 belongs in
`soong/gui/`. This is what keeps the command line usable without a display.

**No setting is hard coded.** A value someone might reasonably change belongs
in `config.yaml` and is read with a default in the constructor. Technical
constants that must not change, such as the 16 kHz alignment sample rate, are
named module constants instead.

**Heavy imports are lazy**, inside the function that uses them, with the
`ImportError` turned into a domain error naming what to install.

**Domain errors, not raw exceptions.** `DownloadError`, `LyricsSourceError`,
`TranscriptionError`, `ForcedAlignmentError`, `RenderError` and
`PendingReviewError` each say which step failed.

**Source files stay plain ASCII.** Characters the title cleaning needs, such as
en dashes or bullets, are written as escapes.

## Adding a pipeline step

1. Add the member to `PipelineStep` in `events.py`, in run order.
2. Write the module as a class taking `Config`, doing its work in one public
   method, emitting `STARTED`, `PROGRESS` and `COMPLETED` through the callback.
3. Call it from `VideoLyricsPipeline.run()`, passing the same `on_event`.
4. Add its label to `_STEP_LABELS` in `gui/progress_widget.py`, the only change
   the desktop app needs.
5. Test the module directly, with stubs for anything external.

## Adding a lyrics backend

Implement the `Transcriber` protocol, which is one method, and inject it:

```python
class MyTranscriber:
    def transcribe(self, audio_path: Path) -> str:
        ...

LyricsSource(config, transcriber=MyTranscriber())
```

Text obtained that way is fallback text, so it goes through the mandatory
review. [Library](/library/) has the full set of injection points.

## Adding a front end

A front end owes the pipeline a `ReviewProvider` implementation and an
`on_event` callback. Everything else is display. Pass an `alignment_gate` too
when it can block the user for a confirmation before the render.

## Dependencies

`pyproject.toml` is the source of truth and `uv.lock` pins the resolution. Add
a dependency there, run `uv sync`, then regenerate the readable mirror:

```bash
uv export --no-hashes -o requirements.txt
```

Two pins are deliberate. `torch` and `torchaudio` come from the CUDA 12.4
index, which provides the cp313 wheels. `transformers` stays below 5.0 because
the Lyricsmith transcription library targets the 4.x Whisper import paths.

## Working on the documentation

The pages under `docs/` are Markdown, and they build into this site with
[Kiln](https://github.com/Laidwin/kiln), configured by `docs.yml` at the
repository root. Kiln runs in Docker, so nothing is added to the Python
environment.

```bash
docker run --rm -p 4321:4321 -v "$PWD":/project ghcr.io/laidwin/kiln serve   # live reload on http://localhost:4321
docker run --rm -v "$PWD":/project ghcr.io/laidwin/kiln build                # static site in site/, git ignored
```

Two conventions keep the site working:

- **Link between pages with absolute paths**, such as
  `[Configuration](/configuration/)`. Kiln adds the base path of the published
  site.
- **Never link out of `docs/`.** Name files at the repository root in code
  formatting instead.

A new page also goes into the `sidebar` list in `docs.yml`, otherwise it is
built but not listed in the navigation.
