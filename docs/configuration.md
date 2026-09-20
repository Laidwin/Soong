# Configuration

Every tunable setting lives in `config.yaml` at the project root. Nothing is
hard coded in the Python code, so changing behaviour never means editing a
module.

## How the file is loaded

`Config.load()` resolves the file in this order:

1. An explicit path, from `--config PATH` or from `Config.load(path)`.
2. The `SOONG_CONFIG` environment variable.
3. `config.yaml` at the project root.

The directory holding the resolved file becomes the **project root**, and every
relative path in the file is resolved against it. Absolute paths are used as
is, so outputs and checkouts can live anywhere.

Sections are reachable as attributes, for example `config.video.blur.sigma`. A
missing key raises an `AttributeError` naming the keys that do exist. A key you
did not declare falls back to the default listed below, so the file can be
trimmed to the settings you actually change.

## Environment variables

| Variable | Used for |
| --- | --- |
| `GENIUS_ACCESS_TOKEN` | The Genius API token. The variable name itself is configurable through `genius.access_token_env`. |
| `SOONG_CONFIG` | Path to an alternative `config.yaml`. |

Both are read from `.env` when it exists, which the two entry points load at
startup. `.env` is git ignored.

## Full reference

### `download`

| Key | Type | Default | Notes |
| --- | --- | --- | --- |
| `format` | str | `bestvideo[height<=1080]+bestaudio/best` | yt-dlp format selector. The merged container keeps its native audio. |
| `output_dir` | str | `./outputs/downloads` | Video and extracted WAV. |

The alignment WAV is always mono at 16 kHz, which the MMS model requires, so it
is a constant in the code rather than a setting.

### `genius`

| Key | Type | Default | Notes |
| --- | --- | --- | --- |
| `access_token_env` | str | `GENIUS_ACCESS_TOKEN` | Name of the variable holding the token. |
| `timeout_seconds` | int | `10` | Per request timeout. |
| `min_match_score` | float | `0.75` | Below this, the result is rejected and the fallback runs. |

Raising `min_match_score` means fewer wrong lyrics and more fallback runs, each
costing a transcription and a human review. Lowering it does the opposite.
[Processing chain](processing-chain.md) explains how the score is computed.

### `lyricsmith`

| Key | Type | Default | Notes |
| --- | --- | --- | --- |
| `project_dir` | str | `./Lyricsmith` | Local checkout of Lyricsmith. Git ignored here. |
| `config_path` | str | empty | Lyricsmith configuration. Empty means `<project_dir>/config.yaml`. |
| `quality_preset` | str | `balanced` | Demucs preset, overridable with `--quality`. |
| `separate` | bool | `true` | Isolate the vocals before transcribing. |

Turning `separate` off is faster and noticeably less accurate.

### `review`

| Key | Type | Default | Notes |
| --- | --- | --- | --- |
| `require_manual_review` | bool | `true` | Enforce the review after a transcription. Genius text never goes to review. |
| `review_dir` | str | `./outputs/review` | Where the command line writes review files. |
| `blocking` | bool | `true` | When false, unvalidated raw text is used. |

### `forced_alignment`

| Key | Type | Default | Notes |
| --- | --- | --- | --- |
| `language` | str | `fra` | ISO 639-3 code for the MMS aligner. |
| `device` | str | `cuda` | `cuda` or `cpu`. Falls back to the CPU on its own when CUDA is missing. |
| `batch_size` | int | `8` | Emission batch size. Lower it when VRAM is short. |
| `romanize` | bool | `true` | Romanise the text, which MMS expects for non Latin scripts. |
| `star_frequency` | str | `segment` | Where star tokens may absorb audio with no matching text. |
| `low_score_threshold` | float | `0.30` | Below this mean confidence, a verse is spread proportionally instead. |

!!! note "`language` is the setting to check first"
    A wrong ISO 639-3 code is by far the most common cause of a globally bad
    alignment. It is `fra`, not `fr`.

### `subtitles`

| Key | Type | Default | Notes |
| --- | --- | --- | --- |
| `mode` | str | `line` | `line` for one cue per verse, `word` for one per word. |
| `font_path` | str | `./assets/fonts/Montserrat-Bold.ttf` | A missing font fails the render explicitly. |
| `font_size` | int | `54` | Pixels. |
| `font_color` | str | `white` | Any ffmpeg colour name or hex value. |
| `outline_color` | str | `black` | Keeps the text readable over any picture. |
| `outline_width` | int | `3` | Pixels. |
| `position` | str | `center` | `bottom`, `center` or `top`. |
| `margin_px` | int | `150` | Distance to the bottom or top edge, ignored when centred. |
| `fade_ms` | int | `150` | Fade in and out. `0` disables the fade. |
| `min_cue_duration_ms` | int | `400` | Floor that stops short words from flashing by. |

### `video`

| Key | Type | Default | Notes |
| --- | --- | --- | --- |
| `blur.filter` | str | `gblur` | ffmpeg blur filter. |
| `blur.sigma` | float | `100` | Blur strength. Large values leave the lyrics as the only readable element. |
| `output_dir` | str | `./outputs/final` | Rendered videos, named `<track_id>.mp4`. |
| `codec` | str | `h264_nvenc` | `libx264`, `h264_nvenc` or `hevc_nvenc`. |
| `crf` | int | `18` | CRF for libx264, the equivalent `-cq` level for NVENC. |
| `preset` | str | `medium` | libx264 presets, or `p1` to `p7` for NVENC. An x264 preset given to NVENC falls back to `p5`. |
| `copy_audio` | bool | `true` | Keep the source audio, re-encoded to AAC 192k. |

### `gui`

| Key | Type | Default | Notes |
| --- | --- | --- | --- |
| `window_title` | str | `Soong Lyrics Studio` | Window and application name. |
| `window_width` | int | `1000` | Initial width. |
| `window_height` | int | `700` | Initial height. |
| `theme` | str | `dark` | `dark` applies the bundled stylesheet, anything else keeps the native look. |

## Tuning for less VRAM

In order of effect, on a card that runs out of memory during the alignment:

1. Lower `forced_alignment.batch_size` from 8 to 4, then to 2.
2. Set `lyricsmith.separate` to false, which skips the Demucs pass entirely on
   fallback runs.
3. Set `forced_alignment.device` to `cpu`. Alignment then takes minutes instead
   of seconds, but has no VRAM limit at all.

The render is unaffected by any of this: NVENC uses the encoder block rather
than the general VRAM pool, and the blur runs on the CPU regardless.

## Tuning for speed

| Change | Effect |
| --- | --- |
| `video.codec: h264_nvenc` | The largest single win on an NVIDIA card |
| `video.blur.sigma` lower | The blur is the slowest filter, and it is CPU bound |
| `video.preset` faster | Trades file size for encoding time |
| A Genius token | Skips the transcription entirely, which is most of a run |
