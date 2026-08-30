from __future__ import annotations

from dataclasses import dataclass

from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.domain.review_state import ReviewState


@dataclass(frozen=True)
class Cue:
    """The product-facing, editable subtitle unit.

    Timing is Cue-level (V1 frozen, see ROADMAP.md section 4). All
    language_layers share this Cue's start_time / end_time.
    """

    id: str
    start_time: float
    end_time: float
    language_layers: tuple[LanguageLayer, ...]
    review_state: ReviewState = ReviewState.PENDING

    def __post_init__(self) -> None:
        if self.start_time < 0:
            raise ValueError("Cue.start_time must not be negative")
        if self.end_time <= self.start_time:
            raise ValueError("Cue.end_time must be after start_time")
        if not self.language_layers:
            raise ValueError("Cue.language_layers must contain at least one layer")
