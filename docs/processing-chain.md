# Processing chain

A run applies these steps, always in this order:

```text
download -> lyrics -> review -> align -> cues -> render
```

The first two gather material, the third is the only one that waits for a
human, and the last three turn text into a video. Every step reports its state
through a `PipelineEvent`, which is what drives the progress screen and the
command line log.

| Step | `PipelineStep` | Reports a percentage | Can be skipped |
| --- | --- | --- | --- |
| Download | `DOWNLOAD` | Yes | No |
| Lyrics | `LYRICS_FETCH` | No | No |
| Review | `REVIEW` | No | Yes, when the text came from Genius |
| Alignment | `FORCED_ALIGNMENT` | Yes | No, but it degrades rather than fails |
| Cue building | `SUBTITLE_BUILD` | No | No |
| Render | `RENDER` | Yes | No |

## 1. Download

yt-dlp fetches the merged video, keeping its native audio track, then a
separate ffmpeg call extracts a mono 16 kHz WAV next to it. Two files, two
purposes: the video is what gets rendered, the WAV is what gets aligned. The
video is never stripped of its audio.

Locating the file that yt-dlp actually wrote needs care. Several `id.*` files
can coexist, and the intermediate video only streams named `id.fNNN.mp4` carry
no audio at all. The path reported by yt-dlp is trusted first, and the glob
fallback prefers the file whose stem is exactly the video id.

The title and artist are parsed here too, from the music metadata when YouTube
exposes it, otherwise from an "Artist - Title" formatted title. Both are then
stripped of promotional noise, because the next step is only as good as those
two strings:

| Raw | Cleaned |
| --- | --- |
| `Le Keur - Vital (Clip Officiel)` | `Le Keur - Vital` |
| `Danger [Official Music Video]` | `Danger` |
| `EL CHAPO (Official Video) \| HD` | `EL CHAPO` |
| `SomeArtistVEVO` | `SomeArtist` |
| `Le Keur - Topic` | `Le Keur` |

A parenthesised group is removed only when nothing meaningful survives the
promotional terms, so `Nouveau Départ (Pt. 2)` keeps its parenthetical. French
and English terms are both recognised, since the noise depends on the uploader
rather than on the song.

## 2. Lyrics

Genius is asked first. A result is scored against the query, and anything below
`genius.min_match_score` is discarded.

The score is a weighted average: the title counts for 0.7 and the artist for
0.3, because channel names vary far more than track names. Each half is a
lenient similarity, the better of a sequence ratio over normalised tokens and a
containment score, meaning the share of query tokens present in the result.
Taking the best of the two is what keeps `Sucrée` matching
`Sucree (feat. Someone)`: the extra words hurt the sequence ratio but not the
containment.

The page is then cleaned. The contributor banner, the trailing `Embed` counter,
the `You might also like` insert and every bracketed section line such as
`[Refrain]` are removed. Those section lines matter: they are never sung, so
leaving them in would feed the aligner words that have no audio.

When Genius has nothing usable, for any reason including a missing token or a
network error, the audio goes to Lyricsmith instead. Its directory and its
vendored `heartlib/src` are put on `sys.path`, its `pipeline` package is
imported, and the configured quality preset is applied. Only the `lyrics` field
is read.

!!! note "Why the transcription timestamps are ignored"
    The transcription model was never trained to preserve Whisper timestamp
    tokens. In practice it returns a single segment covering the whole track,
    from 0.0 to 0.0. Timing comes from step 4 instead, which is exactly what
    that step exists for.

## 3. Review

Text from Genius is considered reliable and goes straight through. Text from a
transcription is not rendered until a human has validated it, because a
transcription error propagates into the timing and then into the picture.

The desktop app shows the [review screen](desktop-app.md). The command line
writes a [review file](output.md) and stops with exit code 2.

Both paths end the same way: `ReviewProvider.request_review()` returns the
final text, possibly corrected.

## 4. Alignment

`ctc-forced-aligner` loads the MMS model, once, on first use, in float16 on
CUDA or float32 on the CPU. The text is flattened to a single stream of words,
aligned against the waveform, and the result is a list of words with a start,
an end and a confidence score.

Those words are then grouped back into the original verses: each line consumes
as many aligned words as it contains. This is what turns a word stream back
into the lines the lyrics were written in.

Three things can go wrong, and none of them stops the run:

| Situation | Response |
| --- | --- |
| A verse scores below `low_score_threshold` | That verse alone is spread proportionally over its window |
| Fewer aligned words than the verse contains | Same spread, over the remaining window |
| A verse ends with no duration | Given between 0.5 and 3 seconds, bounded by the next verse |
| The aligner fails entirely | The whole text is spread proportionally over the track duration |

A proportional spread divides a window by character count, and assigns a score
of 0 to every word it produces, so a degraded verse stays recognisable
downstream.

## 5. Cue building

Verses become `DrawTextCue` objects, one per verse in `line` mode, one per word
in `word` mode using the per word timings the aligner returned. Cues are then
sorted by start time, stripped of empty text, and given at least
`subtitles.min_cue_duration_ms`. Word mode without that floor shows single
frames of text on fast passages.

## 6. Render

One ffmpeg pass blurs the picture and draws every cue, with `-progress pipe:1`
parsed to report the percentage. [Output format](output.md) covers the
filtergraph, the quoting and the encoder arguments.

## Where each step lives

| Step | Module |
| --- | --- |
| Download | `soong/downloader.py` |
| Lyrics | `soong/lyrics_source.py`, `genius_client.py`, `transcriber.py` |
| Review | `soong/review_provider.py`, `gui/gui_review_provider.py` |
| Alignment | `soong/forced_aligner.py` |
| Cue building | `soong/subtitle_builder.py` |
| Render | `soong/renderer.py`, `utils/ffmpeg_utils.py` |
| Orchestration | `soong/pipeline.py` |
