# Troubleshooting

## Setup

### `ffmpeg not found` or `ffprobe not found`

Neither is bundled. Install ffmpeg and put both executables on the `PATH`, or
beside the application. ffprobe ships with ffmpeg, so a missing ffprobe usually
means a partial install.

### `Font not found: ...`

No font ships with the repository. Download one, put it in `assets/fonts/`, and
check that `subtitles.font_path` matches the file name exactly.

### `Configuration file not found`

`config.yaml` is expected at the project root. Use `--config PATH` or set
`SOONG_CONFIG` when running from elsewhere.

### `Lyricsmith checkout not found: ...`

Only the transcription fallback needs it. Either clone Lyricsmith and point
`lyricsmith.project_dir` at it, or work with Genius alone, which means tracks
Genius does not know cannot be processed.

## Lyrics

### Every track goes through the fallback

Check that `.env` exists, that it contains `GENIUS_ACCESS_TOKEN`, and that the
name matches `genius.access_token_env`. The logs say `No Genius token in ...`
when it is missing, and `Genius search failed` on a network or quota error.

### Genius returns the wrong song

The lookup depends entirely on the parsed title and artist. Look at the
`Downloaded: <artist> - <title>` log line: if the parsing went wrong, the match
will too. Raising `genius.min_match_score` rejects weak matches, at the cost of
more fallback runs.

### The lyrics contain `[Refrain]` or a contributor banner

Those are stripped by `strip_genius_artifacts`. If something new slips through,
it belongs in that function rather than in a workaround downstream: section
lines are never sung and would feed the aligner words with no audio.

## Alignment

### The timing is off everywhere

Check `forced_alignment.language` first. It takes an ISO 639-3 code, so `fra`
and not `fr`, and a wrong one is by far the most common cause.

### The timing drifts on some verses only

Those verses fell back to a proportional spread, either because they scored
below `low_score_threshold` or because the aligner returned fewer words than
the verse contains. Spoken intros, background vocals and ad libs present in the
text but not in the audio all cause this. Deleting lines that are not sung, in
the review step, is usually the fix.

### Everything is evenly spaced from start to finish

Alignment failed entirely and the whole text was spread proportionally. The log
says `Forced alignment failed (...): falling back.` and the event message says
so too. The cause is in the exception: a missing library, a CUDA out of memory
error or an unreadable audio file.

### CUDA out of memory

Lower `forced_alignment.batch_size`, or set `forced_alignment.device` to `cpu`,
which is slower and has no VRAM limit. [Configuration](configuration.md) lists
the changes in order of effect. The aligner already switches to the CPU on its
own when CUDA is not available at all.

## Rendering

### The render looks frozen, no progress

Progress comes from `-progress pipe:1`, a global option that must precede the
inputs and outputs. If you edited the ffmpeg arguments, check that ordering
first.

### `No such filter: '<fragment of a lyrics line>'`

A lyrics string reached the filtergraph. It must not: each cue is written to
its own file and read through `textfile=`. Only paths and expressions may be
inlined, and only after quoting.

### The output video has no sound

With `copy_audio`, the audio is re-encoded to AAC rather than copied, precisely
because a copied opus track inside an mp4 often plays silent. If you changed
that to a stream copy, change it back. Also check that the source had an audio
track at all: the mapping uses `0:a?`, which tolerates its absence silently.

### The render is slow even on a GPU

The blur runs on the CPU whatever the encoder. Lower `video.blur.sigma` or
accept the cost. Switching to NVENC only speeds up the encoding half.

### `ffmpeg failed with code ...`

The last 2000 characters of the ffmpeg stderr are in the message. The cause is
almost always in that tail.

## Front ends

### The command keeps exiting with code 2

A review is pending. Open `outputs/review/<track_id>.review.txt`, correct the
lyrics, and replace the **whole first line** with exactly `# VALIDATED`,
including the `#`. Then run the same command again.

### The window is unresponsive during a run

It should not be: the pipeline runs in a worker thread and communicates only
through signals. Code that touches a widget from that thread is the bug, and it
can crash outright rather than merely freeze.

### The app never leaves the review screen

Validating pushes the text into the queue the worker is blocked on. A provider
replaced after the worker started, or a click that never reaches
`submit_review`, leaves the worker waiting forever.
