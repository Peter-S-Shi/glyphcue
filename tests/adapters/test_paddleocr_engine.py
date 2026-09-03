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
    assert regions[0].language == "en"
    assert regions[0].geometry is not None
    assert len(regions[0].geometry) == 4
    assert all(isinstance(pt, tuple) and len(pt) == 2 for pt in regions[0].geometry)


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

    assert engine.supported_languages() == ("en", "zh", "ja")
    info = engine.runtime_info()
    assert info.engine_name == "PaddleOCR"
    assert info.backend == "cpu"
    assert info.version != "unknown"
    assert info.backend_version is not None
    assert info.backend_version != "unknown"


def test_recognize_regions_matches_full_recognize_and_bypasses_detection():
    # Multi-line image to verify transcription, line ordering, and geometry
    image = Image.new("RGB", (400, 140), color=(20, 20, 20))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=24)
    draw.text((10, 10), "First Line Hello", font=font, fill=(255, 255, 255))

    draw.text((10, 55), "Second Line World", font=font, fill=(255, 255, 255))
    draw.text((10, 100), "Third Line GlyphCue", font=font, fill=(255, 255, 255))
    img_arr = np.array(image)

    engine = PaddleOcrEngine(language="en")
    engine.initialize()
    try:
        full_regions = engine.recognize(img_arr)
        assert len(full_regions) == 3

        polygons = [r.geometry for r in full_regions]
        assert all(poly is not None for poly in polygons)

        # Guard: detector MUST NOT be invoked during recognition-only
        pipeline = engine._engine.paddlex_pipeline
        det_called = False

        def _forbidden_det(*args, **kwargs):
            nonlocal det_called
            det_called = True
            raise AssertionError("text_det_model was called during recognize_regions")

        pipeline._pipeline.text_det_model = _forbidden_det

        rec_regions = engine.recognize_regions(img_arr, polygons)

        assert not det_called
        assert len(rec_regions) == len(full_regions)
        for full, rec in zip(full_regions, rec_regions):
            assert rec.text == full.text
            assert rec.geometry == full.geometry
            assert rec.language == full.language
            assert rec.confidence == pytest.approx(full.confidence, rel=1e-3)
    finally:
        engine.shutdown()


def test_recognize_regions_empty_polygons_returns_empty_list():
    engine = PaddleOcrEngine(language="en")
    engine.initialize()
    try:
        res = engine.recognize_regions(_text_image("test"), [])
        assert res == []
    finally:
        engine.shutdown()

