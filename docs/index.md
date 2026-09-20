# Soong

Soong turns a music video into a lyrics video. It downloads the clip, gets the
lyrics text from **Genius** or from a local **Lyricsmith** transcription, aligns
that text against the audio with a **forced aligner**, then renders a blurred
video with the verses burned into the picture.

It is built to run on a single consumer GPU with 8 GB of VRAM, and it falls
back to the CPU when there is none.

## What it produces

One file, named after the track:

```text
outputs/final/le-keur-vital.mp4
```

The picture is blurred, and each verse appears while it is sung, centred, with
an outline that survives any background:

```text
[0:14 - 0:18]  first verse of the song
[0:18 - 0:22]  second verse of the song
[0:22 - 0:25]  third verse of the song
```

Those timestamps come from the alignment, never from the lyrics source. The
same run reports every step as it goes:

```text
[DOWNLOAD/COMPLETED] Downloaded: Le Keur - Vital
[LYRICS_FETCH/COMPLETED] Lyrics from Genius (score 0.96)
[REVIEW/COMPLETED] Reliable lyrics from Genius: no review needed.
[FORCED_ALIGNMENT/COMPLETED 100%] 42 verses aligned.
[SUBTITLE_BUILD/COMPLETED] 42 cues generated.
[RENDER/COMPLETED 100%] Video rendered: le-keur-vital.mp4
```

## Two ways to run it

```bash
uv run python gui_main.py                              # desktop app
uv run python main.py process "https://youtu.be/..."   # command line
```

The desktop app is the main mode: it shows the progress live, and it is where
you proofread the lyrics and check the alignment by ear before committing to a
render. The command line does the same work unattended, with a review file
instead of a review screen.

## The rule the whole project follows

Text and timing come from different places, always. Genius and the
transcription provide text only. Timing is computed by forced alignment against
the audio, because the transcription model returns a single segment covering
the whole track and Genius provides no timing at all.

## Where to go next

| Page | What it covers |
| --- | --- |
| [Installation](installation.md) | Python, ffmpeg, a font, a Genius token, a Lyricsmith checkout |
| [Desktop app](desktop-app.md) | The five screens, the review step, the alignment check |
| [Command line](cli.md) | Arguments, exit codes, the review file cycle |
| [Library](library.md) | Driving the pipeline from your own code |
| [Configuration](configuration.md) | Every key of `config.yaml` |
| [Processing chain](processing-chain.md) | The six steps of a run, in order |
| [Output format](output.md) | The rendered file, the review file, the cue modes |
| [Architecture](architecture.md) | Layers, design decisions, threading, testing |
| [Packaging](packaging.md) | Building the standalone executable |
| [Troubleshooting](troubleshooting.md) | What each failure means |
| [Contributing](contributing.md) | Tests, conventions, extension points |
