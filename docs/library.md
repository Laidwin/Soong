# Library

The pipeline is importable. `main.py` is about eighty lines and is the smallest
complete example of what follows.

```python
from soong import Config, FileReviewProvider, VideoLyricsPipeline

config = Config.load()
pipeline = VideoLyricsPipeline(config, review_provider=FileReviewProvider(config))
final_video = pipeline.run("https://youtube.com/watch?v=...")
```

`run()` returns the `Path` of the rendered file.

## What the package exports

| Name | Kind | Purpose |
| --- | --- | --- |
| `Config` | class | Loads `config.yaml` and resolves paths against the project root |
| `VideoLyricsPipeline` | class | The orchestrator |
| `ReviewProvider` | abstract class | The human validation contract |
| `FileReviewProvider` | class | The file based implementation |
| `PendingReviewError` | exception | Raised while a validation is pending |
| `PipelineEvent`, `PipelineStep`, `StepStatus` | dataclass, enums | The progress events |

Everything else is reachable through its module, for example
`soong.forced_aligner.AlignedLine`.

## Configuration

```python
config = Config.load()                       # config.yaml at the project root
config = Config.load("other.yaml")           # an explicit file
config = Config.load(reload=True)            # ignore the cached instance
```

Sections are reachable as attributes and as items, so a setting can be
overridden before the pipeline is built:

```python
config.subtitles["mode"] = "word"
config.video["codec"] = "libx264"
```

## Following the progress

```python
def on_event(event):
    print(event.step.name, event.status.name, event.progress_pct, event.message)

pipeline.run(url, on_event=on_event)
```

`on_event` is optional. [Processing chain](processing-chain.md) lists what each
step emits, and [Architecture](architecture.md) documents the payloads.

## Replacing the human review

Implement `request_review`, which blocks until the text is validated and
returns the final text:

```python
from soong import ReviewProvider, VideoLyricsPipeline

class AutoApprove(ReviewProvider):
    def request_review(self, raw_text: str, track_id: str) -> str:
        return raw_text

pipeline = VideoLyricsPipeline(config, review_provider=AutoApprove())
```

That example approves a transcription nobody read, which is exactly what the
review exists to prevent. A real implementation posts the text somewhere a
human can see it and waits.

## Replacing the transcription backend

`LyricsSource` takes both collaborators, so another backend is one object:

```python
from pathlib import Path
from soong.lyrics_source import LyricsSource

class MyTranscriber:
    def transcribe(self, audio_path: Path) -> str:
        return "first verse\nsecond verse"

source = LyricsSource(config, transcriber=MyTranscriber())
```

The `Transcriber` protocol is that single method. Text obtained this way is
treated as fallback text, so it still goes through the review.

## Stopping before the render

`alignment_gate` receives the aligned verses and returns the verses to render.
It may block, and it may change them. The desktop app uses it for its alignment
check screen.

```python
def gate(lines):
    for line in lines:
        print(f"{line.start:7.2f} {line.text}")
    return lines

pipeline.run(url, on_event=on_event, alignment_gate=gate)
```

## Errors

| Exception | Raised when |
| --- | --- |
| `DownloadError` | yt-dlp failed or produced no usable media |
| `LyricsSourceError` | No source returned any text |
| `TranscriptionError` | The Lyricsmith checkout is missing or failed |
| `ForcedAlignmentError` | Alignment failed, caught internally and replaced by the proportional fallback |
| `PendingReviewError` | A file review is pending |
| `RenderError` | ffmpeg failed, or the font is missing |

All of them derive from `RuntimeError`.
