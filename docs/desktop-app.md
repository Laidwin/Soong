# Desktop app

```bash
uv run python gui_main.py
```

The desktop app is the main way to use Soong. It is the only mode where you can
proofread the lyrics while listening to the track, and check the alignment by
ear before paying for a render.

It is built with PySide6, under the LGPL, which is what makes shipping a
standalone executable possible. See [Packaging](packaging.md).

## The five screens

| Screen | When it appears | What you do |
| --- | --- | --- |
| URL | At the start | Paste the link, press Start or Enter |
| Progress | Between every other screen | Watch the steps, the percentage and the log |
| Review | Only after a transcription fallback | Correct the lyrics while playing the track |
| Alignment check | After every alignment | Click verses to hear them, then render |
| Done | At the end | Open the output folder, or start another video |

Navigation is automatic. The app returns to the progress screen whenever the
worker resumes, and to the URL screen after a failure.

## 1. URL

One field and one button. The URL is whatever yt-dlp accepts, so a `youtu.be`
short link works as well as a full watch URL. An empty field is refused.

The Start button is disabled while a run is in progress, so a second run cannot
be launched over the first.

## 2. Progress

Six step rows, one per pipeline step, each with a marker: `...` while pending,
`>` while running, `OK` when done, `FAIL` on failure. Below them, a progress
bar fed by the steps that can measure themselves, namely the download, the
alignment phases and the ffmpeg render.

The log view under the bar receives every pipeline event and every log record,
including those emitted by Lyricsmith during a transcription. That is
deliberate: a long transcription with no output looks like a hang, and this is
where you see it working.

## 3. Review

This screen appears only when the lyrics came from the transcription fallback,
where a human validation is mandatory. It shows the raw text in an editable
area, one line per verse, next to a player loaded with the downloaded audio.

Play the track, fix what the model misheard, remove lines that are not sung,
then validate. The Validate button stays disabled while the text is empty.

Validating releases the worker thread immediately and the run continues into
the alignment. There is no second run and no file to edit, unlike the command
line.

!!! note "Why there is no verse seeking here"
    Alignment has not happened yet at this point, so no verse has a timestamp
    to seek to. The player is there to listen to the track while proofreading.
    Seeking per verse is the next screen.

## 4. Alignment check

Every verse with its real timestamps, as
`[0:14 - 0:18]  first verse of the song`. Click one and the player seeks to its
start and plays, which is the fastest way to tell whether the alignment holds.

Two buttons close the screen:

- **Start the render** hands the verses back to the worker, which renders them.
- **Align again** returns to the URL screen after submitting the current
  alignment, so the worker is never left blocked. Adjust
  `forced_alignment.language` or the quality preset in `config.yaml` first,
  since those are the settings that change the result.

This screen exists because an ffmpeg render is long and an alignment problem is
obvious in five seconds of listening.

## 5. Done

The path of the rendered file, a button that opens its folder in the system
file manager, and a button that returns to the URL screen for another video.

## Responsiveness

The pipeline runs in a worker thread and never touches a widget. The window
stays responsive during the download, the transcription, the alignment and the
render, and the two screens that need an answer block that worker rather than
the interface. [Architecture](architecture.md) describes the handoff.

## Theme

`gui.theme: dark` applies the bundled stylesheet. Any other value keeps the
native Qt look of the platform. The window title and initial size are
configurable too, under `gui` in [Configuration](configuration.md).
