# Packaging

```bash
uv run pyinstaller build_exe.spec
```

The build is described in a versioned `.spec` file rather than an ad hoc
command line, so it is reproducible and reviewable.

## What goes in

| Included | Why |
| --- | --- |
| `soong` and its submodules | The application |
| `config.yaml` | The runtime configuration, next to the executable |
| `assets/fonts/`, `assets/icons/` | The font `drawtext` needs, and the window icon |
| `ctc_forced_aligner` | Imported dynamically, so it must be declared |
| Lyricsmith `pipeline` and `heartlib/src` | Only when the checkout exists |

The spec reads the Lyricsmith location from `config.yaml` rather than keeping a
second copy of that path. When the directory is absent it prints a notice and
continues, producing a build without the transcription fallback, which is a
valid build for a Genius only workflow.

## What stays out

**Model checkpoints and `ffmpeg.exe`.** Several gigabytes, and the whole reason
the executable stays a reasonable size. They must be present on the machine
that runs it: ffmpeg on the `PATH` or beside the executable, checkpoints where
the configuration expects them. A missing one is reported explicitly rather
than failing silently.

**Tests and pytest**, through `excludes`. **Virtual environments**, which the
spec never references.

## Expectations

CUDA builds of `torch` and `torchaudio` inflate the output from several hundred
megabytes to a few gigabytes. That is normal, not a misconfiguration.

The first launch of a one file build is slow, because the archive is unpacked
to a temporary directory.

!!! warning "Test on a machine without Python"
    DLL errors are common with PyInstaller and CUDA, and they only appear
    outside the development machine, where the missing library happens to be
    installed anyway.

## Runtime layout

```text
SoongLyricsStudio.exe
config.yaml
assets/fonts/<your font>.ttf
ffmpeg.exe, ffprobe.exe      (or anywhere on the PATH)
outputs/                     (created on first run)
```

Paths in `config.yaml` resolve against the directory holding that file, so this
layout works with no edit.
