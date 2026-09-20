# Contributing

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
review. [Library](library.md) has the full set of injection points.

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

The pages under `docs/` are Markdown, readable on GitHub, and they build into
this site with MkDocs and the Material theme. Both live in a `docs` dependency
group, so an ordinary `uv sync` does not install them.

```bash
uv run --group docs mkdocs serve   # live reload on http://127.0.0.1:8000
uv run --group docs mkdocs build   # static site in site/, git ignored
```

Two conventions keep both rendering paths working:

- **Link between pages with relative Markdown paths**, such as
  `[Configuration](configuration.md)`. GitHub and MkDocs both resolve those.
- **Never link out of `docs/`.** A link to a file at the repository root works
  on GitHub and breaks the site build, so name such files in code formatting
  instead.

A new page also goes into the `nav` list in `mkdocs.yml`, otherwise the
validation settings report it as omitted.
