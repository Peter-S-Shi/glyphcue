import pytest

pytest.importorskip("paddleocr", reason="paddleocr is an optional, heavy V1 OCR dependency")

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from glyphcue.adapters.ocr_engine import OcrEngine
from glyphcue.adapters.ocr_types import OcrInitializationError, OcrRecognitionError, OcrTextRegion
from glyphcue.adapters.paddleocr_engine import PaddleOcrEngine


def _text_image(text: str) -> np.ndarray:
    image = Image.new("RGB", (300, 50), color=(20, 20, 20))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("arial.ttf", 24)
    draw.text((8, 10), text, font=font, fill=(255, 255, 255))
    return np.array(image)


def test_paddleocr_engine_satisfies_the_ocr_engine_protocol():
    engine: OcrEngine = PaddleOcrEngine()

    assert isinstance(engine, OcrEngine)


def test_recognize_returns_normalized_text_regions_not_vendor_dicts():
    engine = PaddleOcrEngine()
    engine.initialize()
    try:
        regions = engine.recognize(_text_image("Hello world"))
    finally:
        engine.shutdown()

    assert len(regions) == 1
    assert isinstance(regions[0], OcrTextRegion)
    assert regions[0].text == "Hello world"
    assert 0.0 < regions[0].confidence <= 1.0


def test_recognize_before_initialize_raises_a_normalized_error():
    engine = PaddleOcrEngine()

    with pytest.raises(OcrRecognitionError):
        engine.recognize(_text_image("anything"))


def test_initialize_failure_is_normalized_not_a_vendor_exception(monkeypatch):
    import glyphcue.adapters.paddleocr_engine as module

    def _boom(**kwargs):
        raise RuntimeError("vendor blew up during model load")

    monkeypatch.setattr(module, "_construct_paddleocr", _boom)
    engine = PaddleOcrEngine()

    with pytest.raises(OcrInitializationError):
        engine.initialize()


def test_supported_languages_and_runtime_info_are_reported():
    engine = PaddleOcrEngine()

    assert "en" in engine.supported_languages()
    info = engine.runtime_info()
    assert info.engine_name == "PaddleOCR"
    assert info.backend == "cpu"
