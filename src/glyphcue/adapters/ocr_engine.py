from collections.abc import Sequence
from typing import Any, Protocol, runtime_checkable

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
        """GlyphCue canonical language/script codes this implementation
        can be configured to recognize (e.g. via its constructor) --
        not the subset already loaded/initialized by this particular
        instance. A constructed-for-"en" instance still reports every
        code the implementation supports, since recognize() results
        only ever reflect the language it was constructed for; callers
        needing another language construct a separate instance for it.
        """
        ...

    def runtime_info(self) -> OcrRuntimeInfo:
        """Identify the concrete runtime/model/backend in use."""
        ...

    def shutdown(self) -> None:
        """Release runtime resources. Safe to call more than once."""
        ...


@runtime_checkable
class RegionOcrEngine(OcrEngine, Protocol):
    """An OcrEngine that supports recognition-only on pre-localized text regions.

    Eliminates redundant text detection when region geometry (e.g. from an
    external text detector in Hybrid mode) is already available. Implementations
    must catch vendor exceptions and raise OcrRecognitionError, returning only
    GlyphCue-normalized OcrTextRegion items.
    """

    def recognize_regions(
        self,
        image: object,
        regions: Sequence[Any],
    ) -> list[OcrTextRegion]:
        """Run recognition on pre-localized polygon regions within image.

        Raises OcrRecognitionError (never a vendor exception) on failure.
        """
        ...


