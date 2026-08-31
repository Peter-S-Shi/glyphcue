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


@dataclass(frozen=True)
class OcrRuntimeInfo:
    """Identifies which OCR runtime/model produced a result, for
    provenance and diagnostics -- never for domain logic branching."""

    engine_name: str
    version: str
    backend: str


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
