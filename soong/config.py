"""Centralised loading and access to the project configuration (`config.yaml`).

A `Config` object exposes each YAML section as an attribute (for example
``config.video.blur.sigma``) and resolves relative paths against the project
root. No tunable setting is hard coded anywhere else in the code base.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

import yaml

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"

_CONFIG_PATH_ENV = "SOONG_CONFIG"


class AttrDict(dict):
    """Dictionary whose keys are also reachable as attributes."""

    def __getattr__(self, item: str) -> Any:
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(
                f"Missing configuration key: '{item}'. "
                f"Available keys: {list(self.keys())}"
            ) from exc

    def __setattr__(self, key: str, value: Any) -> None:
        self[key] = value


def _wrap(value: Any) -> Any:
    """Recursively turn nested dictionaries into `AttrDict` instances."""
    if isinstance(value, dict):
        return AttrDict({k: _wrap(v) for k, v in value.items()})
    if isinstance(value, list):
        return [_wrap(v) for v in value]
    return value


@dataclass
class Config:
    """Video pipeline configuration, loaded from a YAML file."""

    path: Path
    download: AttrDict = field(default_factory=AttrDict)
    genius: AttrDict = field(default_factory=AttrDict)
    lyricsmith: AttrDict = field(default_factory=AttrDict)
    review: AttrDict = field(default_factory=AttrDict)
    forced_alignment: AttrDict = field(default_factory=AttrDict)
    subtitles: AttrDict = field(default_factory=AttrDict)
    video: AttrDict = field(default_factory=AttrDict)
    gui: AttrDict = field(default_factory=AttrDict)

    SECTIONS: ClassVar[tuple[str, ...]] = (
        "download",
        "genius",
        "lyricsmith",
        "review",
        "forced_alignment",
        "subtitles",
        "video",
        "gui",
    )

    _cached: ClassVar[Config | None] = None

    @classmethod
    def load(cls, path: str | Path | None = None, *, reload: bool = False) -> Config:
        """Load the configuration, or return the cached instance.

        Args:
            path: Path to an alternative `config.yaml`. When omitted, the
                ``SOONG_CONFIG`` environment variable is read, then the default
                file at the project root.
            reload: Read the file again even when an instance is already cached.
        """
        if cls._cached is not None and not reload and path is None:
            return cls._cached

        resolved = cls._resolve_config_path(path)
        if not resolved.exists():
            raise FileNotFoundError(f"Configuration file not found: {resolved}")

        with resolved.open("r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}

        instance = cls(
            path=resolved,
            **{section: _wrap(raw.get(section, {})) for section in cls.SECTIONS},
        )
        cls._cached = instance
        return instance

    @staticmethod
    def _resolve_config_path(path: str | Path | None) -> Path:
        if path is not None:
            return Path(path).expanduser().resolve()
        env_path = os.environ.get(_CONFIG_PATH_ENV)
        if env_path:
            return Path(env_path).expanduser().resolve()
        return _DEFAULT_CONFIG_PATH

    @property
    def project_root(self) -> Path:
        """Project root, that is the directory holding `config.yaml`."""
        return self.path.parent

    def resolve_path(self, value: str | Path) -> Path:
        """Resolve a configured path relative to the project root."""
        candidate = Path(value).expanduser()
        if candidate.is_absolute():
            return candidate
        return (self.project_root / candidate).resolve()
