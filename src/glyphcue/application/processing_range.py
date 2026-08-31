from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProcessingRange:
    """Whole-media or selected start/end range for Path A processing.

    Preserves the source timeline by default: resolved bounds are always
    absolute seconds within the source media, never renumbered relative
    to the selection.
    """

    start_time: float | None = None
    end_time: float | None = None

    def is_whole_media(self) -> bool:
        return self.start_time is None and self.end_time is None

    def resolve(self, media_duration_seconds: float) -> tuple[float, float]:
        """Resolves against the real media duration, rejecting a range
        that could never correspond to real media (ROADMAP M9): a
        reversed or zero-duration range, a negative start, or an end
        beyond the media's own real length. Never silently clamps or
        renumbers -- an invalid selection is refused, not guessed at,
        so an invalid UI selection can never reach an OCR job or become
        a final Cue's timing."""
        start = self.start_time if self.start_time is not None else 0.0
        end = self.end_time if self.end_time is not None else media_duration_seconds
        if start < 0:
            raise ValueError("Processing range start must not be negative")
        if end <= start:
            raise ValueError("Processing range end must be after start")
        if end > media_duration_seconds:
            raise ValueError("Processing range end must not exceed the media's real duration")
        return start, end
