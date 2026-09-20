"""Lyrics overlay video pipeline.

Takes a music video URL, fetches the lyrics text (Genius first, local
transcription as a fallback), aligns that text against the audio through forced
alignment, then renders a blurred video with the lyrics burned into the pixels.

High level API, for library use::

    from soong import Config, VideoLyricsPipeline, FileReviewProvider

    config = Config.load()
    pipeline = VideoLyricsPipeline(config, review_provider=FileReviewProvider(config))
    final_video = pipeline.run("https://youtube.com/watch?v=...")
"""

from __future__ import annotations

from .config import Config
from .events import PipelineEvent, PipelineStep, StepStatus
from .pipeline import VideoLyricsPipeline
from .review_provider import FileReviewProvider, PendingReviewError, ReviewProvider

__version__ = "0.1.0"

__all__ = [
    "Config",
    "VideoLyricsPipeline",
    "PipelineEvent",
    "PipelineStep",
    "StepStatus",
    "ReviewProvider",
    "FileReviewProvider",
    "PendingReviewError",
]
