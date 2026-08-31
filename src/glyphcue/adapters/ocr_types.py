from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OcrTextRegion:
    """One GlyphCue-normalized piece of recognized text.

    This is deliberately not an Observation: OCR alone has no timing
    context (that comes from the calling frame-analysis pipeline in a
    later milestone). Vendor result objects never cross the OcrEngine
    boundary -- only this type does.
    """

    text: str
    confidence: float
    language: str | None = None
    geometry: tuple[tuple[float, float], ...] | None = None
    """Vendor-neutral region polygon, or None if the engine reports none.

    When present: a polygon of (x, y) pixel-coordinate points in the same
    coordinate space as the image passed to recognize() (origin top-left,
    y increasing downward -- standard image-array indexing), in the point
    order the engine reported them. No vendor box/polygon type ever
    crosses the OcrEngine boundary -- only this plain tuple-of-tuples
    does.
    """


@dataclass(frozen=True)
class OcrRuntimeInfo:
    """Identifies which OCR runtime/model produced a result, for
    provenance and diagnostics -- never for domain logic branching."""

    engine_name: str
    version: str
    backend: str
    backend_version: str | None = None
    """Version of the underlying compute backend/runtime library (e.g.
    PaddlePaddle's own version), kept distinct from `version` (the OCR
    package's own version) because compatibility issues can be specific
    to one (package, backend) version pairing -- see
    docs/adr/0001-ocr-runtime-selection.md for a real example. None if
    the engine cannot identify a separate backend version.
    """


class OcrError(Exception):
    """Base class for all GlyphCue-normalized OCR errors.

    Concrete OcrEngine implementations must catch vendor-specific
    exceptions internally and re-raise one of these; no vendor exception
    type may cross the OcrEngine boundary.
    """


class OcrInitializationError(OcrError):
    """Raised when an OCR runtime fails to initialize."""


class OcrRecognitionError(OcrError):
    """Raised when an OCR runtime fails during recognition."""
