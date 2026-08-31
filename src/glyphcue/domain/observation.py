from __future__ import annotations

from dataclasses import dataclass

from glyphcue.domain.provenance import Provenance
from glyphcue.domain.roi import ROI


@dataclass(frozen=True)
class Observation:
    """Raw machine/source evidence that later reconstruction turns into a Cue."""

    id: str
    text: str
    start_time: float
    end_time: float
    provenance: Provenance
    language: str | None = None
    confidence: float | None = None
    """OCR engine score for this observation's text, 0..1. None for
    non-OCR provenance (e.g. subtitle-file import) or engines that don't
    report one."""
    roi: ROI | None = None
    """The region this observation was read from, in fractional
    frame coordinates. None for non-frame-based provenance."""
    geometry: tuple[tuple[float, float], ...] | None = None
    """Vendor-neutral text-region polygon, in the pixel-coordinate space
    of the (typically ROI-cropped) image passed to OcrEngine.recognize()
    -- see OcrTextRegion.geometry. None if the engine reported none."""
    frame_reference: str | None = None
    """A reproducible locator for the source frame this observation was
    read from (e.g. "<path>@<pts>s"), sufficient to re-decode the same
    frame for verification. None for non-frame-based provenance."""

    def __post_init__(self) -> None:
        if self.start_time < 0:
            raise ValueError("Observation.start_time must not be negative")
        if self.end_time <= self.start_time:
            raise ValueError("Observation.end_time must be after start_time")
