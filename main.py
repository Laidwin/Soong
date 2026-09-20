"""Command line entry point, always available without the desktop UI.

Examples::

    python main.py process "https://youtube.com/watch?v=..." --quality best --mode word
    python main.py process "https://youtu.be/..."   # after validating the review file

The command line uses `FileReviewProvider`: when a human validation is required,
because the lyrics come from the transcription fallback, a review file is
written and the command stops. Edit and validate that file, then run the same
command again.
"""

from __future__ import annotations

import typer

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from soong.config import Config
from soong.events import PipelineEvent
from soong.pipeline import VideoLyricsPipeline
from soong.review_provider import FileReviewProvider, PendingReviewError
from soong.utils.logger import get_logger

app = typer.Typer(add_completion=False, help="Lyrics overlay video pipeline.")
logger = get_logger("cli")

EXIT_FAILED = 1
EXIT_PENDING_REVIEW = 2


def _log_event(event: PipelineEvent) -> None:
    logger.info("%s", event)


@app.command()
def process(
    url: str = typer.Argument(..., help="URL of the music video to process."),
    quality: str = typer.Option(
        None, "--quality", help="Transcription quality preset (fast|balanced|best)."
    ),
    mode: str = typer.Option(None, "--mode", help="Subtitle mode (line|word)."),
    config_path: str = typer.Option(
        None, "--config", help="Path to an alternative config.yaml."
    ),
) -> None:
    """Download, fetch the lyrics, align them and render the video."""
    config = Config.load(config_path, reload=True)
    if quality:
        config.lyricsmith["quality_preset"] = quality
    if mode:
        config.subtitles["mode"] = mode

    # The command line always reviews through a file, never through the UI.
    pipeline = VideoLyricsPipeline(config, review_provider=FileReviewProvider(config))

    try:
        final_path = pipeline.run(url, on_event=_log_event)
    except PendingReviewError as exc:
        typer.secho(str(exc), fg=typer.colors.YELLOW)
        raise typer.Exit(code=EXIT_PENDING_REVIEW)
    except Exception as exc:
        typer.secho(f"Failed: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=EXIT_FAILED)

    typer.secho(f"Video rendered: {final_path}", fg=typer.colors.GREEN)


@app.command()
def gui() -> None:
    """Start the desktop application, same as `python gui_main.py`."""
    from soong.gui.app import run

    raise typer.Exit(code=run(Config.load()))


if __name__ == "__main__":
    app()
