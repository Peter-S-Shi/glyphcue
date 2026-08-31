from __future__ import annotations

from typing import Protocol, runtime_checkable

from glyphcue.adapters.ocr_types import OcrRuntimeInfo, OcrTextRegion


@runtime_checkable
class OcrEngine(Protocol):
    """Boundary isolating a specific OCR runtime (e.g. RapidOCR, PaddleOCR).

    Frozen for V1 (ROADMAP.md Milestone 3). Exact runtime/model selection
    is decided by benchmark evidence, not this contract (see
    docs/adr/0001-ocr-runtime-selection.md). No vendor object or vendor
    exception type may ever cross this boundary: recognize() returns
    only OcrTextRegion, and initialize()/recognize() raise only
    OcrError subclasses (see ocr_types.py).
    """

    def initialize(self) -> None:
        """Load models / warm up the runtime.

        Raises OcrInitializationError (never a vendor exception) on
        failure.
        """
        ...

    def recognize(self, image: object) -> list[OcrTextRegion]:
        """Run recognition on a single frame/ROI image.

        Raises OcrRecognitionError (never a vendor exception) on
        failure.
        """
        ...

    def supported_languages(self) -> tuple[str, ...]:
        """Language/script codes this engine can recognize."""
        ...

    def runtime_info(self) -> OcrRuntimeInfo:
        """Identify the concrete runtime/model/backend in use."""
        ...

    def shutdown(self) -> None:
        """Release runtime resources. Safe to call more than once."""
        ...
