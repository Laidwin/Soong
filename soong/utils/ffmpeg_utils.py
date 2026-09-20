"""Subprocess wrapper around `ffmpeg` and `ffprobe`.

Isolating the external calls here keeps `renderer.py` readable and lets the
tests monkeypatch them. ffmpeg is NOT bundled in the executable: its presence is
checked before a render through `ensure_ffmpeg`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Callable, Iterator

from .logger import get_logger

logger = get_logger("ffmpeg")

_ERROR_TAIL_CHARS = 2000


class FFmpegError(RuntimeError):
    """An ffmpeg or ffprobe call failed."""


def ffmpeg_path() -> str:
    """Path to the ffmpeg executable, or raise `FFmpegError`."""
    executable = shutil.which("ffmpeg")
    if executable is None:
        raise FFmpegError(
            "ffmpeg not found. Install it and add it to PATH, "
            "or put ffmpeg.exe next to the application."
        )
    return executable


def ffprobe_path() -> str:
    """Path to the ffprobe executable, or raise `FFmpegError`."""
    executable = shutil.which("ffprobe")
    if executable is None:
        raise FFmpegError(
            "ffprobe not found. It ships with ffmpeg, so check your PATH."
        )
    return executable


def ensure_ffmpeg() -> None:
    """Check that both ffmpeg and ffprobe are available."""
    ffmpeg_path()
    ffprobe_path()


def probe_duration(media_path: Path) -> float:
    """Return the duration of a media file in seconds, 0 when unknown."""
    cmd = [
        ffprobe_path(),
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(media_path),
    ]
    try:
        completed = subprocess.run(
            cmd, check=True, capture_output=True, text=True, encoding="utf-8"
        )
    except subprocess.CalledProcessError as exc:
        raise FFmpegError(f"ffprobe failed on {media_path}: {exc.stderr}") from exc

    data = json.loads(completed.stdout or "{}")
    try:
        return float(data["format"]["duration"])
    except (KeyError, TypeError, ValueError):
        return 0.0


def run_with_progress(
    args: list[str],
    *,
    total_duration: float,
    on_progress: Callable[[float], None] | None = None,
) -> None:
    """Run ffmpeg, reporting progress parsed from ``-progress pipe:1``.

    Args:
        args: ffmpeg arguments WITHOUT the executable and without ``-progress``,
            both of which are added here.
        total_duration: Target duration in seconds, used to compute a percentage.
        on_progress: Called with a percentage between 0 and 100.
    """
    cmd = [
        ffmpeg_path(),
        "-y",
        "-hide_banner",
        "-nostats",
        "-progress",
        "pipe:1",
        *args,
    ]
    logger.info("ffmpeg: %s", " ".join(cmd))
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    stderr_chunks: list[str] = []

    def drain_stderr() -> None:
        if process.stderr is not None:
            stderr_chunks.extend(process.stderr)

    stderr_thread = threading.Thread(target=drain_stderr, daemon=True)
    stderr_thread.start()

    try:
        for block in _iter_progress(process):
            if on_progress is None or total_duration <= 0:
                continue
            seconds = _block_seconds(block)
            if seconds is not None:
                on_progress(max(0.0, min(100.0, seconds / total_duration * 100.0)))
    finally:
        exit_code = process.wait()
        stderr_thread.join(timeout=5.0)

    if exit_code != 0:
        tail = "".join(stderr_chunks)[-_ERROR_TAIL_CHARS:]
        raise FFmpegError(f"ffmpeg failed with code {exit_code}:\n{tail}")
    if on_progress is not None:
        on_progress(100.0)


def extract_wav(
    video_path: Path,
    out_path: Path,
    *,
    sample_rate: int = 16000,
    mono: bool = True,
) -> Path:
    """Extract the audio track of a video into a PCM WAV file.

    Used to produce the audio the forced aligner consumes, while the source
    video keeps its own native audio track for the final render.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_path(),
        "-y",
        "-hide_banner",
        "-v",
        "error",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1" if mono else "2",
        "-ar",
        str(sample_rate),
        "-c:a",
        "pcm_s16le",
        str(out_path),
    ]
    completed = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if completed.returncode != 0:
        raise FFmpegError(
            f"Audio extraction failed:\n{completed.stderr[-_ERROR_TAIL_CHARS:]}"
        )
    return out_path


def _iter_progress(process: subprocess.Popen) -> Iterator[dict[str, str]]:
    """Yield the ``-progress pipe:1`` blocks of ffmpeg, one key=value per line."""
    block: dict[str, str] = {}
    if process.stdout is None:
        return
    for line in process.stdout:
        line = line.strip()
        if not line or "=" not in line:
            continue
        key, _, value = line.partition("=")
        block[key] = value
        if key == "progress":
            yield block
            block = {}


def _block_seconds(block: dict[str, str]) -> float | None:
    """Output position of a progress block in seconds, `None` when unusable."""
    raw = block.get("out_time_us") or block.get("out_time_ms")
    if not raw or not raw.lstrip("-").isdigit():
        return None
    return int(raw) / 1_000_000
