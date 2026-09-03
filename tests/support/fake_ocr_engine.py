from __future__ import annotations

from glyphcue.adapters.ocr_types import (
    OcrInitializationError,
    OcrRecognitionError,
    OcrRuntimeInfo,
    OcrTextRegion,
)


class FakeOcrEngine:
    """A fully controllable OcrEngine implementation for tests.

    Proves application/test code can completely replace a real OCR
    runtime: no vendor package needs to be installed to test any code
    that depends only on the OcrEngine contract.
    """

    def __init__(
        self,
        regions: list[OcrTextRegion] | None = None,
        languages: tuple[str, ...] = ("en",),
        runtime_info: OcrRuntimeInfo | None = None,
        fail_initialize_with: Exception | None = None,
        fail_recognize_with: Exception | None = None,
    ) -> None:
        self._regions = regions if regions is not None else []
        self._languages = languages
        self._runtime_info = runtime_info or OcrRuntimeInfo(
            engine_name="fake", version="0.0", backend="cpu"
        )
        self._fail_initialize_with = fail_initialize_with
        self._fail_recognize_with = fail_recognize_with
        self.initialized = False
        self.shutdown_call_count = 0
        self.recognize_call_count = 0

    def initialize(self) -> None:
        if self._fail_initialize_with is not None:
            raise OcrInitializationError(str(self._fail_initialize_with)) from self._fail_initialize_with
        self.initialized = True

    def recognize(self, image: object) -> list[OcrTextRegion]:
        self.recognize_call_count += 1
        if self._fail_recognize_with is not None:
            raise OcrRecognitionError(str(self._fail_recognize_with)) from self._fail_recognize_with
        return list(self._regions)

    def supported_languages(self) -> tuple[str, ...]:
        return self._languages

    def runtime_info(self) -> OcrRuntimeInfo:
        return self._runtime_info

    def shutdown(self) -> None:
        self.shutdown_call_count += 1
        self.initialized = False


class FakeRegionOcrEngine(FakeOcrEngine):
    """Test fake that implements RegionOcrEngine."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.recognize_regions_call_count = 0
        self.received_regions: list[object] = []

    def recognize_regions(
        self, image: object, regions: object
    ) -> list[OcrTextRegion]:
        self.recognize_regions_call_count += 1
        self.received_regions.append(regions)
        if self._fail_recognize_with is not None:
            raise OcrRecognitionError(str(self._fail_recognize_with)) from self._fail_recognize_with
        return list(self._regions)

