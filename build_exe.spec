# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller configuration packaging the desktop application.

Build::

    pyinstaller build_exe.spec

Things to keep in mind, also documented in the README:
- Model checkpoints and ffmpeg.exe are NOT bundled, as they weigh several
  gigabytes. They must sit next to the executable, and their absence is
  reported at startup rather than failing silently.
- The Lyricsmith checkout lives outside this repository. Only its `pipeline`
  package and its vendored `heartlib/src` are bundled, never its virtual
  environment, tests or examples.
- torch and torchaudio with CUDA make the build much bigger, which is expected.
"""

from pathlib import Path

import yaml
from PyInstaller.utils.hooks import collect_submodules

PROJECT_ROOT = Path(SPECPATH)

# The Lyricsmith checkout is configured in config.yaml, so the spec reads it
# from there instead of hard coding a second copy of the path.
_config = yaml.safe_load((PROJECT_ROOT / "config.yaml").read_text(encoding="utf-8"))
_lyricsmith_setting = _config.get("lyricsmith", {}).get("project_dir", "./Lyricsmith")
LYRICSMITH_DIR = (PROJECT_ROOT / _lyricsmith_setting).resolve()

datas = [
    (str(PROJECT_ROOT / "config.yaml"), "."),
    (str(PROJECT_ROOT / "assets" / "fonts"), "assets/fonts"),
    (str(PROJECT_ROOT / "assets" / "icons"), "assets/icons"),
]

hiddenimports = collect_submodules("soong") + ["ctc_forced_aligner"]
pathex = [str(PROJECT_ROOT)]

if LYRICSMITH_DIR.exists():
    datas += [
        (str(LYRICSMITH_DIR / "config.yaml"), "Lyricsmith"),
        (str(LYRICSMITH_DIR / "pipeline"), "Lyricsmith/pipeline"),
        (str(LYRICSMITH_DIR / "heartlib" / "src"), "Lyricsmith/heartlib/src"),
    ]
    hiddenimports += collect_submodules("pipeline")
    pathex.append(str(LYRICSMITH_DIR))
else:
    print(
        f"[build_exe.spec] Lyricsmith not found at {LYRICSMITH_DIR}: "
        f"the build will ship without the transcription fallback."
    )

# Nothing from the test suites belongs in the executable.
excludes = ["tests", "pytest"]

a = Analysis(
    ["gui_main.py"],
    pathex=pathex,
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="SoongLyricsStudio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # windowed application
    disable_windowed_traceback=False,
    icon=str(PROJECT_ROOT / "assets" / "icons" / "app.ico"),
)
