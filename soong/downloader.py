"""YouTube clip download plus audio extraction, driven by yt-dlp.

`VideoDownloader.download(url)` returns a `DownloadResult` holding the video
file, a 16 kHz mono WAV expected by the forced aligner, and the title and artist
parsed out of the YouTube metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .config import Config
from .events import PipelineEvent, PipelineStep, StepStatus
from .utils import ffmpeg_utils
from .utils.logger import get_logger
from .utils.text_utils import clean_artist_name, clean_youtube_title

logger = get_logger("downloader")

EventCallback = Callable[[PipelineEvent], None]

ALIGNMENT_SAMPLE_RATE = 16000


class DownloadError(RuntimeError):
    """The download or the audio extraction failed."""


@dataclass
class DownloadResult:
    """Everything the rest of the pipeline needs from the download step."""

    video_path: Path
    audio_path: Path
    title: str
    artist: str
    duration_seconds: float
    source_url: str


def _emit(
    cb: EventCallback | None, status: StepStatus, message: str = "", **kw: Any
) -> None:
    if cb is not None:
        cb(PipelineEvent(PipelineStep.DOWNLOAD, status, message, **kw))


def _split_title_artist(info: dict[str, Any]) -> tuple[str, str]:
    """Guess (title, artist) from the yt-dlp metadata.

    yt-dlp sometimes exposes ``artist`` and ``track`` from the YouTube music
    metadata; otherwise it falls back to ``uploader`` and an "Artist - Title"
    formatted title. Both fields are then stripped of promotional noise such as
    "(Official Video)" or "- Topic" to make the Genius lookup more reliable.
    """
    track = info.get("track")
    meta_artist = info.get("artist") or info.get("creator")
    if track and meta_artist:
        title, artist = str(track), str(meta_artist)
    else:
        raw = str(info.get("title", "")).strip()
        if " - " in raw:
            left, _, right = raw.partition(" - ")
            title, artist = right.strip(), left.strip()
        else:
            title, artist = raw, str(info.get("uploader", "") or "")

    title = clean_youtube_title(title) or title
    artist = clean_artist_name(artist)
    return (title or "unknown"), (artist or "unknown")


class VideoDownloader:
    """Download a clip and extract the audio track the aligner needs."""

    def __init__(self, config: Config) -> None:
        self.output_dir = config.resolve_path(
            config.download.get("output_dir", "./outputs/downloads")
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.video_format = config.download.get(
            "format", "bestvideo[height<=1080]+bestaudio/best"
        )

    def download(
        self, url: str, on_event: EventCallback | None = None
    ) -> DownloadResult:
        """Download `url` and return the resulting media and metadata.

        Raises:
            DownloadError: when yt-dlp fails or produces no usable media.
        """
        try:
            from yt_dlp import YoutubeDL
        except ImportError as exc:
            raise DownloadError(
                "yt-dlp is not installed (see requirements.txt)."
            ) from exc

        _emit(on_event, StepStatus.STARTED, f"Downloading {url}")

        ydl_opts: dict[str, Any] = {
            "format": self.video_format,
            "outtmpl": str(self.output_dir / "%(id)s.%(ext)s"),
            "merge_output_format": "mp4",
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "progress_hooks": [self._make_hook(on_event)],
        }

        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
        except Exception as exc:
            _emit(on_event, StepStatus.FAILED, str(exc))
            raise DownloadError(f"Download failed: {exc}") from exc

        if info is None:
            raise DownloadError("yt-dlp returned no information.")

        video_id = info.get("id", "video")
        video_path = self._resolve_video_path(info, video_id)
        if video_path is None or not video_path.exists():
            raise DownloadError(f"No video file found for {url}.")

        _emit(on_event, StepStatus.PROGRESS, "Extracting audio.")
        audio_path = self.output_dir / f"{video_id}.wav"
        try:
            ffmpeg_utils.extract_wav(
                video_path, audio_path, sample_rate=ALIGNMENT_SAMPLE_RATE, mono=True
            )
        except ffmpeg_utils.FFmpegError as exc:
            _emit(on_event, StepStatus.FAILED, str(exc))
            raise DownloadError(f"Audio extraction failed: {exc}") from exc

        title, artist = _split_title_artist(info)
        duration = float(info.get("duration") or 0.0)
        _emit(
            on_event,
            StepStatus.COMPLETED,
            f"Downloaded: {artist} - {title}",
            payload={
                "title": title,
                "artist": artist,
                "audio_path": str(audio_path),
                "video_path": str(video_path),
            },
        )
        logger.info("Download finished: %s - %s", artist, title)
        return DownloadResult(
            video_path=video_path,
            audio_path=audio_path,
            title=title,
            artist=artist,
            duration_seconds=duration,
            source_url=url,
        )

    def _resolve_video_path(self, info: dict[str, Any], video_id: str) -> Path | None:
        """Locate the MERGED container, the only file that carries audio.

        The path reported by yt-dlp is trusted first, as it stays correct even
        when several `id.*` files coexist. The glob fallback prefers the file
        whose stem is exactly the video id, avoiding the intermediate video only
        streams named `id.fNNN.<ext>`.
        """
        for download in info.get("requested_downloads") or []:
            reported = download.get("filepath") or download.get("_filename")
            if (
                reported
                and Path(reported).exists()
                and Path(reported).suffix.lower() != ".wav"
            ):
                return Path(reported)
        if info.get("filepath"):
            return Path(info["filepath"])

        candidates = [
            path
            for path in self.output_dir.glob(f"{video_id}.*")
            if path.suffix.lower() != ".wav"
        ]
        for suffix in (".mp4", ".mkv", ".webm"):
            for path in candidates:
                if path.stem == video_id and path.suffix.lower() == suffix:
                    return path
        for suffix in (".mp4", ".mkv", ".webm"):
            for path in sorted(candidates):
                if path.suffix.lower() == suffix:
                    return path
        return sorted(candidates)[0] if candidates else None

    @staticmethod
    def _make_hook(on_event: EventCallback | None) -> Callable[[dict], None]:
        def hook(status: dict) -> None:
            if status.get("status") != "downloading":
                return
            total = status.get("total_bytes") or status.get("total_bytes_estimate")
            done = status.get("downloaded_bytes")
            pct = (done / total * 100.0) if (total and done) else None
            _emit(on_event, StepStatus.PROGRESS, "Downloading.", progress_pct=pct)

        return hook
