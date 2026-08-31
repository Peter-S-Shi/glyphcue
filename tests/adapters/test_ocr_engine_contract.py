import pytest

from glyphcue.adapters.ocr_engine import OcrEngine
from glyphcue.adapters.ocr_types import (
    OcrInitializationError,
    OcrRecognitionError,
    OcrRuntimeInfo,
    OcrTextRegion,
)
from tests.support.fake_ocr_engine import FakeOcrEngine


def test_fake_engine_satisfies_the_ocr_engine_protocol():
    engine: OcrEngine = FakeOcrEngine()

    assert isinstance(engine, OcrEngine)


def test_recognize_returns_normalized_text_regions_not_vendor_objects():
    engine = FakeOcrEngine(regions=[OcrTextRegion(text="hello", confidence=0.95)])
    engine.initialize()

    result = engine.recognize(image=object())

    assert result == [OcrTextRegion(text="hello", confidence=0.95)]
    engine.shutdown()


def test_supported_languages_returns_a_tuple_of_codes():
    engine = FakeOcrEngine(languages=("en", "ja", "zh"))

    assert engine.supported_languages() == ("en", "ja", "zh")


def test_runtime_info_reports_engine_identity():
    engine = FakeOcrEngine(
        runtime_info=OcrRuntimeInfo(engine_name="fake", version="1.0", backend="cpu")
    )

    info = engine.runtime_info()

    assert info == OcrRuntimeInfo(engine_name="fake", version="1.0", backend="cpu")


def test_initialization_failure_is_raised_as_a_normalized_error_not_a_vendor_exception():
    engine = FakeOcrEngine(fail_initialize_with=RuntimeError("vendor blew up"))

    with pytest.raises(OcrInitializationError):
        engine.initialize()


def test_recognition_failure_is_raised_as_a_normalized_error_not_a_vendor_exception():
    engine = FakeOcrEngine(fail_recognize_with=ValueError("vendor decode error"))
    engine.initialize()

    with pytest.raises(OcrRecognitionError):
        engine.recognize(image=object())


def test_shutdown_is_idempotent_and_does_not_raise():
    engine = FakeOcrEngine()
    engine.initialize()

    engine.shutdown()
    engine.shutdown()
