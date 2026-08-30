from __future__ import annotations

from typing import Protocol

from glyphcue.domain.observation import Observation


class OcrEngine(Protocol):
    """Boundary isolating a specific OCR runtime (e.g. RapidOCR, PaddleOCR).

    Exact runtime/model selection remains benchmark-dependent (see
    ROADMAP.md Milestone 3) and is not decided by this contract. Vendor
    result objects must never cross this boundary — only Observation.
    """

    def initialize(self) -> None:
        """Load models / warm up the runtime."""
        ...

    def recognize(self, image: object) -> list[Observation]:
        """Run recognition on a single frame/ROI image and return Observations."""
        ...

    def shutdown(self) -> None:
        """Release runtime resources."""
        ...
