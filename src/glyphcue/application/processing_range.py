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
        start = self.start_time if self.start_time is not None else 0.0
        end = self.end_time if self.end_time is not None else media_duration_seconds
        return start, end
