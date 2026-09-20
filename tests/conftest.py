"""Shared fixtures for the video pipeline tests.

The tests need neither a GPU nor ffmpeg, torch or yt-dlp: the heavy
dependencies are imported lazily by the code and monkeypatched where needed.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from soong.config import Config


@pytest.fixture()
def config(tmp_path: Path) -> Config:
    """The real config.yaml, with every output redirected to a temp folder."""
    config = Config.load(PROJECT_ROOT / "config.yaml", reload=True)
    config.review["review_dir"] = str(tmp_path / "review")
    config.video["output_dir"] = str(tmp_path / "final")
    config.download["output_dir"] = str(tmp_path / "downloads")
    return config
