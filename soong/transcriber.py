"""Fallback lyrics text: local transcription through the Lyricsmith project.

Lyricsmith is a separate repository (Demucs vocal separation plus a fine tuned
Whisper style transcriber). It is not a pip installable library, so it is used
from a checkout on disk: its directory is added to `sys.path` and its `pipeline`
package is imported.

Only the transcribed TEXT is consumed here. The timestamped `segments` it
returns are deliberately ignored: the model was never trained to preserve
Whisper timestamp tokens and collapses the whole track into a single segment.
Timing always comes from forced alignment instead.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Protocol

from .config import Config
from .utils.logger import get_logger

logger = get_logger("transcriber")


class TranscriptionError(RuntimeError):
    """The local transcription backend is unavailable or failed."""


class Transcriber(Protocol):
    """Contract used by `LyricsSource` to obtain fallback lyrics text."""

    def transcribe(self, audio_path: Path) -> str:
        """Return the transcribed lyrics of an audio file, one verse per line."""


class LyricsmithTranscriber:
    """`Transcriber` backed by a local checkout of the Lyricsmith project."""

    def __init__(self, config: Config) -> None:
        settings = config.lyricsmith
        self.project_dir = config.resolve_path(
            settings.get("project_dir", "./Lyricsmith")
        )
        configured_config = settings.get("config_path")
        self.config_path = (
            config.resolve_path(configured_config)
            if configured_config
            else self.project_dir / "config.yaml"
        )
        self.quality_preset = settings.get("quality_preset")
        self.separate = bool(settings.get("separate", True))

    def transcribe(self, audio_path: Path) -> str:
        """Run the Lyricsmith pipeline and return its lyrics text."""
        lyrics_pipeline_cls, config_cls = self._import_lyricsmith()

        if not self.config_path.exists():
            raise TranscriptionError(
                f"Lyricsmith configuration file not found: {self.config_path}"
            )
        lyricsmith_config = config_cls.load(self.config_path, reload=True)
        if self.quality_preset:
            lyricsmith_config.models.demucs["quality_preset"] = self.quality_preset

        logger.info(
            "Transcribing %s with Lyricsmith (vocal separation: %s).",
            audio_path.name,
            self.separate,
        )
        result = lyrics_pipeline_cls(lyricsmith_config).run(
            Path(audio_path), separate=self.separate
        )
        return result.transcription.lyrics

    def _import_lyricsmith(self) -> tuple[Any, Any]:
        """Import the Lyricsmith `pipeline` package from its checkout.

        Two directories go on `sys.path`: the project root, which exposes the
        `pipeline` package, and `heartlib/src`, which holds the vendored
        transcription library. Lyricsmith loads only the single transcription
        module out of heartlib, so its heavy optional dependencies are never
        needed here.
        """
        if not self.project_dir.exists():
            raise TranscriptionError(
                f"Lyricsmith checkout not found: {self.project_dir}. "
                f"Clone it and point lyricsmith.project_dir in config.yaml at it."
            )

        heartlib_src = self.project_dir / "heartlib" / "src"
        for path in (str(self.project_dir), str(heartlib_src)):
            if path not in sys.path:
                sys.path.insert(0, path)

        try:
            from pipeline import Config as LyricsmithConfig
            from pipeline import LyricsPipeline
        except ImportError as exc:
            raise TranscriptionError(
                f"Could not import the Lyricsmith `pipeline` package: {exc}"
            ) from exc
        return LyricsPipeline, LyricsmithConfig
