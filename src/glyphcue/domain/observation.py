from __future__ import annotations

from dataclasses import dataclass

from glyphcue.domain.provenance import Provenance


@dataclass(frozen=True)
class Observation:
    """Raw machine/source evidence that later reconstruction turns into a Cue."""

    id: str
    text: str
    start_time: float
    end_time: float
    provenance: Provenance
    language: str | None = None

    def __post_init__(self) -> None:
        if self.start_time < 0:
            raise ValueError("Observation.start_time must not be negative")
        if self.end_time <= self.start_time:
            raise ValueError("Observation.end_time must be after start_time")
