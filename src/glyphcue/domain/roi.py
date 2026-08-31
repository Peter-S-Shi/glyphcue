from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ROI:
    """A region of interest, in fractional frame coordinates (0..1).

    Resolution-independent by design: a Track Group's ROI is defined once
    and applies regardless of the exact pixel dimensions of a given
    source video.
    """

    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        if self.width <= 0:
            raise ValueError("ROI.width must be positive")
        if self.height <= 0:
            raise ValueError("ROI.height must be positive")
        if self.x < 0 or self.y < 0:
            raise ValueError("ROI.x/y must not be negative")
        if self.x + self.width > 1.0:
            raise ValueError("ROI must not extend past the right edge of the frame")
        if self.y + self.height > 1.0:
            raise ValueError("ROI must not extend past the bottom edge of the frame")
