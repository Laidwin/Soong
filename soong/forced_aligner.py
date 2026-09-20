"""Forced alignment between audio and text, using `ctc-forced-aligner` (MMS).

This is the ONLY source of timing in the pipeline. Timestamps coming from the
transcription backend or from Genius are never used.

Robustness: when a line aligns with a low confidence score, or when the library
fails altogether, timings fall back to a proportional split based on character
counts rather than aborting the run.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .config import Config
from .events import PipelineEvent, PipelineStep, StepStatus
from .utils.logger import get_logger
from .utils.text_utils import flatten_for_alignment, normalize_lines, tokenize_words

logger = get_logger("forced_aligner")

EventCallback = Callable[[PipelineEvent], None]

_MIN_PATCHED_DURATION = 0.5
_MAX_PATCHED_DURATION = 3.0


class ForcedAlignmentError(RuntimeError):
    """Forced alignment failed and cannot be recovered at this level."""


@dataclass
class AlignedWord:
    """A word with its time bounds in seconds and a confidence score."""

    text: str
    start: float
    end: float
    score: float = 1.0


@dataclass
class AlignedLine:
    """A verse with its time bounds and the words it is made of."""

    text: str
    start: float
    end: float
    words: list[AlignedWord]

    @property
    def score(self) -> float:
        """Mean confidence of the words, 0 when the line has none."""
        if not self.words:
            return 0.0
        return sum(word.score for word in self.words) / len(self.words)


def _emit(
    cb: EventCallback | None, status: StepStatus, message: str = "", **kw: Any
) -> None:
    if cb is not None:
        cb(PipelineEvent(PipelineStep.FORCED_ALIGNMENT, status, message, **kw))


class ForcedAligner:
    """Align a text against an audio track and group the result into verses."""

    def __init__(self, config: Config) -> None:
        alignment = config.forced_alignment
        self.language = alignment.get("language", "fra")
        self.device = alignment.get("device", "cuda")
        self.batch_size = int(alignment.get("batch_size", 8))
        self.romanize = bool(alignment.get("romanize", True))
        self.star_frequency = alignment.get("star_frequency", "segment")
        self.low_score_threshold = float(alignment.get("low_score_threshold", 0.30))
        self._model = None
        self._tokenizer = None

    def align(
        self,
        audio_path: Path,
        text: str,
        on_event: EventCallback | None = None,
    ) -> list[AlignedWord]:
        """Align `text` against `audio_path` and return the timestamped words.

        Raises:
            ForcedAlignmentError: when the library fails. The proportional
                fallback is applied by the caller, which still holds the
                original text and the track duration.
        """
        _emit(
            on_event, StepStatus.STARTED, "Forced alignment starting.", progress_pct=0.0
        )
        self._ensure_model()

        try:
            from ctc_forced_aligner import (
                generate_emissions,
                get_alignments,
                get_spans,
                load_audio,
                postprocess_results,
                preprocess_text,
            )
        except ImportError as exc:
            raise ForcedAlignmentError(str(exc)) from exc

        flat_text = flatten_for_alignment(text)
        if not flat_text:
            raise ForcedAlignmentError("Empty text: nothing to align.")

        try:
            waveform = load_audio(
                str(audio_path), self._model.dtype, self._model.device
            )
            _emit(
                on_event,
                StepStatus.PROGRESS,
                "Generating emissions.",
                progress_pct=25.0,
            )
            emissions, stride = generate_emissions(
                self._model, waveform, batch_size=self.batch_size
            )
            _emit(
                on_event,
                StepStatus.PROGRESS,
                "Running CTC alignment.",
                progress_pct=60.0,
            )
            tokens_starred, text_starred = preprocess_text(
                flat_text,
                romanize=self.romanize,
                language=self.language,
                star_frequency=self.star_frequency,
            )
            segments, scores, blank_token = get_alignments(
                emissions, tokens_starred, self._tokenizer
            )
            spans = get_spans(tokens_starred, segments, blank_token)
            word_timestamps = postprocess_results(text_starred, spans, stride, scores)
        except Exception as exc:
            _emit(on_event, StepStatus.FAILED, f"Alignment failed: {exc}")
            raise ForcedAlignmentError(str(exc)) from exc

        words = [
            AlignedWord(
                text=str(item.get("text", "")),
                start=float(item.get("start", 0.0)),
                end=float(item.get("end", 0.0)),
                score=float(item.get("score", 1.0)),
            )
            for item in word_timestamps
            if str(item.get("text", "")).strip()
        ]
        _emit(
            on_event,
            StepStatus.PROGRESS,
            f"{len(words)} words aligned.",
            progress_pct=90.0,
        )
        return words

    def group_into_lines(
        self,
        words: list[AlignedWord],
        original_text: str,
        *,
        total_duration: float = 0.0,
    ) -> list[AlignedLine]:
        """Rebuild the verses of `original_text` from the aligned words.

        Each original line consumes as many aligned words as it contains. When a
        line aligns below the confidence threshold, or when words are missing,
        its timings are spread proportionally over the available window.
        """
        lines = normalize_lines(original_text)
        if not lines:
            return []

        global_start = words[0].start if words else 0.0
        global_end = words[-1].end if words else total_duration

        aligned_lines: list[AlignedLine] = []
        cursor = 0
        previous_end = global_start
        for line in lines:
            expected = len(tokenize_words(line))
            line_words = words[cursor : cursor + expected]
            cursor += expected

            if len(line_words) == expected and line_words:
                start = line_words[0].start
                end = max(line_words[-1].end, start)
                aligned = AlignedLine(text=line, start=start, end=end, words=line_words)
                if aligned.score < self.low_score_threshold:
                    aligned = self._proportional_line(line, start, end)
            else:
                window_end = line_words[-1].end if line_words else previous_end
                aligned = self._proportional_line(
                    line, previous_end, max(window_end, previous_end)
                )
            aligned_lines.append(aligned)
            previous_end = aligned.end

        self._patch_zero_windows(aligned_lines, global_end)
        return aligned_lines

    @staticmethod
    def proportional_alignment(
        original_text: str, total_duration: float
    ) -> list[AlignedLine]:
        """Last resort alignment without audio: spread verses by character count.

        Used when forced alignment fails completely, so that a run still
        produces a video instead of stopping.
        """
        lines = normalize_lines(original_text)
        if not lines:
            return []
        weights = [max(len(line), 1) for line in lines]
        total_weight = sum(weights)
        aligned: list[AlignedLine] = []
        cursor = 0.0
        for line, weight in zip(lines, weights):
            duration = (
                total_duration * (weight / total_weight) if total_duration > 0 else 2.0
            )
            aligned.append(
                ForcedAligner._proportional_line(line, cursor, cursor + duration)
            )
            cursor += duration
        return aligned

    def _ensure_model(self) -> None:
        """Load the MMS alignment model once, on first use."""
        if self._model is not None:
            return
        try:
            import torch
            from ctc_forced_aligner import load_alignment_model
        except ImportError as exc:
            raise ForcedAlignmentError(
                "ctc-forced-aligner or torch is not installed (see requirements.txt)."
            ) from exc

        device = self.device
        if device == "cuda" and not torch.cuda.is_available():
            logger.warning("CUDA is unavailable: aligning on CPU instead.")
            device = "cpu"
        dtype = torch.float16 if device == "cuda" else torch.float32
        logger.info("Loading the MMS alignment model on %s (%s).", device, dtype)
        self._model, self._tokenizer = load_alignment_model(device, dtype=dtype)

    @staticmethod
    def _proportional_line(line: str, start: float, end: float) -> AlignedLine:
        """Spread the words of one line proportionally to their length."""
        words = tokenize_words(line)
        end = max(end, start)
        total_chars = sum(len(word) for word in words) or 1
        span = end - start
        spread: list[AlignedWord] = []
        cursor = start
        for word in words:
            duration = span * (len(word) / total_chars)
            spread.append(
                AlignedWord(text=word, start=cursor, end=cursor + duration, score=0.0)
            )
            cursor += duration
        return AlignedLine(text=line, start=start, end=end, words=spread)

    @staticmethod
    def _patch_zero_windows(lines: list[AlignedLine], global_end: float) -> None:
        """Give a minimum duration to lines whose start equals their end."""
        for index, line in enumerate(lines):
            if line.end > line.start:
                continue
            next_start = (
                lines[index + 1].start if index + 1 < len(lines) else global_end
            )
            line.end = max(
                line.start + _MIN_PATCHED_DURATION,
                min(next_start, line.start + _MAX_PATCHED_DURATION),
            )
