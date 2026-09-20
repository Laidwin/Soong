# Output format

## What a run writes

| Path | Contents | Kept |
| --- | --- | --- |
| `outputs/downloads/<video_id>.mp4` | The downloaded clip, with its native audio | Yes |
| `outputs/downloads/<video_id>.wav` | Mono 16 kHz audio, for the alignment | Yes |
| `outputs/review/<track_id>.review.txt` | Pending or validated lyrics, command line only | Yes |
| `outputs/final/<track_id>.mp4` | The rendered video | Yes |
| `outputs/final/<track_id>.filtergraph.txt` | The ffmpeg filter script | No, deleted after the render |
| `outputs/final/.<track_id>_texts/` | One text file per cue | No, deleted after the render |

The two temporary items are removed even when the render fails, so a failed run
leaves nothing behind but its logs.

All of `outputs/` is git ignored: it is heavy and reproducible.

## The track id

`slugify("<artist>-<title>")` produces the `track_id`: ASCII, lowercase,
hyphenated, capped at 80 characters. `Le Keur` and `Sucrée, Pt. 2` become
`le-keur-sucree-pt-2`, which names both the review file and the rendered video.

## The rendered video

| Property | Value |
| --- | --- |
| Container | mp4 |
| Video codec | `video.codec`, H.264 by default |
| Pixel format | `yuv420p`, which every player and platform accepts |
| Audio | AAC at 192k when `video.copy_audio` is true, otherwise none |
| Resolution and frame rate | Unchanged from the source |

The picture is blurred with `gblur` and the lyrics are drawn into the pixels.
There is no subtitle track: the text cannot be turned off, which is the point.

## The review file

```text
# Remove this help line, correct the lyrics below, then replace
# the WHOLE first line with exactly: # VALIDATED
first verse of the song
second verse of the song
```

One verse per line. The file is read again on the next run of the same command:
if its first line is exactly `# VALIDATED`, everything below it is used as the
lyrics. Anything else means the review is still pending, and the run stops with
exit code 2.

Empty lines are dropped and runs of spaces are collapsed when the text is
normalised, so formatting does not have to be exact. Lines that are not sung,
such as a spoken intro left by the transcription, should be deleted rather than
kept: the aligner would otherwise look for audio that does not exist.

## Cue modes

`subtitles.mode` decides what a cue is.

**`line`**, the default, shows one verse at a time, from the start of its first
word to the end of its last:

```text
[0:14.20 - 0:18.05]  first verse of the song
[0:18.05 - 0:22.40]  second verse of the song
```

**`word`** shows one word at a time, using the per word timings:

```text
[0:14.20 - 0:14.55]  first
[0:14.55 - 0:14.90]  verse
[0:14.90 - 0:15.10]  of
```

Word mode is only as good as the alignment, since every error becomes visible
on its own. It also relies on `min_cue_duration_ms` to keep short words
readable.

## The filtergraph

The render is one ffmpeg pass. The graph blurs the video once and chains one
`drawtext` per cue:

```text
[0:v]gblur=sigma=100,drawtext=...,drawtext=...,...[v]
```

Each `drawtext` carries the font file, the text file, the styling from
`subtitles`, `x=(w-text_w)/2` to centre the text, a `y` expression derived from
`position` and `margin_px`, an `alpha` expression implementing the fade, and
`enable=between(t,start,end)`, which is what makes a cue appear and disappear.

### Why the lyrics are in files

Every cue is written to its own UTF-8 file, which `drawtext` reads through
`textfile=`. Apostrophes, commas, colons, accents and percent signs then need
no escaping at all.

This is not a theoretical concern. A French line such as `j'ai vu l'amour`
passed inline breaks the graph with `No such filter: '<fragment>'`, because a
literal apostrophe inside a quoted filter value has to be written as
`'\''`, and a colon stays special even inside quotes.

Paths and expressions, which the project generates itself, are still quoted and
escaped, which is what makes a Windows drive letter work as `C\:/Fonts/...`.
The whole graph is written to a file and passed as `-filter_complex_script`, so
the shell never sees it either.

### Encoder arguments

| Codec | Arguments |
| --- | --- |
| `libx264` | `-crf <crf> -preset <preset>` |
| `h264_nvenc`, `hevc_nvenc` | `-preset <p1..p7> -rc vbr -cq <crf> -b:v 0` |

NVENC has no `-crf`: constant quality is expressed as `-cq` in VBR mode with no
bitrate target. An x264 preset such as `veryslow` is not valid for NVENC, so it
falls back to `p5` rather than failing the render.

### Audio

With `copy_audio`, the source audio is mapped as `0:a?`, which tolerates an
input without audio, and re-encoded to AAC. Stream copying looks cheaper, but
an opus track copied as is into an mp4 very often plays silent, so the
re-encode is deliberate.

## Progress output

ffmpeg runs with `-nostats -progress pipe:1`, and each block is parsed for
`out_time_us`, or `out_time_ms` on older builds, both of which hold
microseconds despite the name. Divided by the duration probed with ffprobe,
that gives the percentage reported by `PipelineEvent(RENDER, PROGRESS)`.

On a non zero exit code, the last 2000 characters of the ffmpeg stderr are
included in the `RenderError`, which is almost always where the cause is.
