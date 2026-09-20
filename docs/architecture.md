# Architecture

## Layers

```text
main.py    ->  pipeline.py  ->  downloader.py / lyrics_source.py  ->  utils/
gui_main.py         |                       |
                    |                       \-> genius_client.py / transcriber.py
                    |-> forced_aligner.py -> utils/text_utils.py
                    |-> subtitle_builder.py
                    \-> renderer.py -------> utils/ffmpeg_utils.py
```

| Element | Layer | Responsibility |
| --- | --- | --- |
| `events.py` | Entities | `PipelineEvent`, `PipelineStep`, `StepStatus` |
| `config.py` | Entities | `Config`, section access, path resolution |
| `downloader.py` | Steps | yt-dlp download, WAV extraction, metadata parsing |
| `genius_client.py` | Steps | Genius lookup and match scoring |
| `transcriber.py` | Steps | Lyricsmith adapter, the `Transcriber` protocol |
| `lyrics_source.py` | Steps | Chooses between the two text sources |
| `review_provider.py` | Steps | The `ReviewProvider` contract and its file implementation |
| `forced_aligner.py` | Steps | MMS alignment, verse grouping, proportional fallbacks |
| `subtitle_builder.py` | Steps | Verses and words into `DrawTextCue` |
| `renderer.py` | Steps | Filtergraph construction and the ffmpeg run |
| `pipeline.py` | Orchestration | Chains the steps, emits events |
| `gui/` | Front end | PySide6, the only package importing Qt |
| `utils/` | Support | ffmpeg calls, text handling, logging |

Data crosses those boundaries as plain dataclasses:

```text
URL -> DownloadResult -> LyricsResult -> validated text
    -> list[AlignedWord] -> list[AlignedLine] -> list[DrawTextCue] -> Path
```

Each arrow is what makes a step testable on its own, without the machinery
behind it.

## Design decisions

### The core never imports Qt

`pipeline.py` knows two abstractions: `ReviewProvider`, for obtaining a human
validation, and `PipelineEvent`, for reporting progress. The command line
injects `FileReviewProvider` and logs the events; the desktop app injects
`GuiReviewProvider` and re-emits them as Qt signals.

Neither changes the behaviour of the pipeline, and the command line runs on a
machine where Qt is not usable at all. Any module importing PySide6 belongs in
`soong/gui/`, without exception.

### Collaborators are injected, not constructed

`LyricsSource(config, genius_client=..., transcriber=...)` builds its own
defaults when nothing is passed. That single decision is what lets the tests
exercise source selection with two ten line stubs, with no network, no model
and no monkeypatching of private methods.

The same applies to the pipeline, which takes its `ReviewProvider`, and to the
optional `alignment_gate`.

### Heavy imports are lazy

`torch`, `yt_dlp`, `lyricsgenius` and `ctc_forced_aligner` are imported inside
the function that uses them, and each `ImportError` is turned into a domain
error naming what to install. Importing a module therefore never pulls in
several gigabytes of CUDA, which is why the test suite runs in half a second.

### Failures degrade, they do not hide

| Failure | Response |
| --- | --- |
| Genius unavailable or unconvincing | Falls back to transcription, logged |
| A verse aligns badly | That verse is spread proportionally, its words scored 0 |
| Alignment fails entirely | The whole text is spread proportionally, with an event saying so |
| Transcription backend missing | `TranscriptionError`, the run stops |
| No text at all | `LyricsSourceError`, the run stops |
| ffmpeg or font missing | `RenderError`, the run stops |

A degraded result is always announced, both as a log record and as a
`PipelineEvent`, and it is always recognisable downstream through the zero
scores.

### Timing has exactly one source

The pipeline could take timestamps from the transcription, and they would be
free. They are also worthless, since the model returns one segment for the
whole track. Genius provides none. Forced alignment is therefore the only
source, which keeps one answer to the question "why is this verse here" rather
than three that disagree.

## The event model

```python
@dataclass
class PipelineEvent:
    step: PipelineStep
    status: StepStatus          # STARTED, PROGRESS, COMPLETED, FAILED
    message: str = ""
    progress_pct: float | None = None
    payload: dict | None = None
```

`payload` carries what a front end needs:

| Step and status | Payload |
| --- | --- |
| `DOWNLOAD` / `COMPLETED` | `title`, `artist`, `audio_path`, `video_path` |
| `LYRICS_FETCH` / `COMPLETED` after a fallback | `raw_text`, `track_id` |
| `REVIEW` / `STARTED` | `raw_text`, `track_id` |

The desktop app keeps `audio_path` from the download event and uses it to play
the track on both review screens.

## Threading

The pipeline is long and blocking, so it runs in a `QThread`. Qt forbids
touching widgets from a secondary thread, and two steps need an answer from the
user in the middle of the run. Both use the same handoff: a signal out, a
`queue.Queue` to block on, a method the interface calls to unblock.

```text
worker thread                          main thread
-------------                          -----------
request_review(text)
  emit review_requested  ---------->   show the review screen
  queue.get()  (blocks)                user edits, clicks Validate
                         <----------   submit_review(text)
  returns the validated text
```

The alignment gate is identical, with `alignment_ready` and
`submit_alignment`. When the user asks to align again, the current alignment is
submitted first, otherwise the worker would wait forever on a queue nobody will
fill.

`GuiReviewProvider` inherits from both `QObject` and an abstract base class,
which needs a metaclass combining the Shiboken metaclass with `ABCMeta`. That
is what `_QtABCMeta` is for.

## Platform notes

### Windows paths in ffmpeg filters

A drive letter contains a colon, which ffmpeg reads as an option separator even
inside a quoted value. Paths are therefore written with forward slashes and
their colons escaped, giving `C\:/Fonts/Montserrat-Bold.ttf`.

### Global ffmpeg options

`-progress pipe:1` and `-nostats` are global options and must precede the
inputs and outputs. Placed after them, ffmpeg silently attaches no progress
reporter and the render looks frozen for its entire duration.

### stderr deadlocks

A verbose filtergraph fills the stderr pipe buffer while the reader is busy
with stdout, which deadlocks the process. stderr is drained in a background
thread for that reason, and its tail is kept for the error message.

## Testing strategy

The suite runs in well under a second and needs no GPU, no ffmpeg, no network
and no model. Two properties make that possible: heavy dependencies are
imported lazily, and collaborators are injected.

| Layer | How it is tested |
| --- | --- |
| Pure functions, `utils/` | Directly, with literal inputs |
| Steps with collaborators | With stubs, through the constructor |
| Steps with an external process | By inspecting what is built, not by running it |
| Threading | With a real thread, asserting the absence of a deadlock |
| Qt widgets | Not tested, the logic worth testing was kept out of them |

`test_renderer.py` is the clearest example of the third row: it asserts that
the filtergraph is correct and that the lyrics never appear in it, without
invoking ffmpeg once.
