"""Pure-Python DirectMlOcrEngine contract tests.

Deliberately NOT gated by pytest.importorskip("rapidocr"): these only
exercise language validation, result-shape conversion, and protocol
conformance, all monkeypatched at the `_construct_rapidocr` seam, so they
never import the real rapidocr/onnxruntime-directml packages. This lets
normal Python 3.12 CI (which does not install the Windows-only [directml]
extra) still cover the normalized contract. Tests that exercise the real
vendor runtime live in test_directml_ocr_engine.py, gated by importorskip
and a Windows platform check.
"""

from __future__ import annotations

import pytest

from glyphcue.adapters.ocr_engine import OcrEngine, RegionOcrEngine
import glyphcue.adapters.directml_ocr_engine as module
from glyphcue.adapters.directml_ocr_engine import DirectMlOcrEngine


def test_directml_ocr_engine_satisfies_ocr_engine_and_region_ocr_engine_protocols():
    engine = DirectMlOcrEngine()
    assert isinstance(engine, OcrEngine)
    assert isinstance(engine, RegionOcrEngine)


def test_unsupported_language_raises_value_error():
    with pytest.raises(ValueError, match="Unsupported language"):
        DirectMlOcrEngine(language="klingon")


def test_recognize_before_initialize_raises_a_normalized_error():
    engine = DirectMlOcrEngine()

    with pytest.raises(module.OcrRecognitionError):
        engine.recognize(image=object())


def test_recognize_regions_before_initialize_raises_a_normalized_error():
    engine = DirectMlOcrEngine()

    with pytest.raises(module.OcrRecognitionError):
        engine.recognize_regions(image=object(), regions=[[0, 0], [10, 0], [10, 5], [0, 5]])


def test_initialize_failure_is_normalized_not_a_vendor_exception(monkeypatch):
    def _boom(**kwargs):
        raise RuntimeError("vendor blew up during model load")

    monkeypatch.setattr(module, "_construct_rapidocr", _boom)
    engine = DirectMlOcrEngine()

    with pytest.raises(module.OcrInitializationError):
        engine.initialize()


def test_recognize_regions_with_empty_regions_returns_empty_list_immediately(monkeypatch):
    monkeypatch.setattr(module, "_construct_rapidocr", lambda **_: object())
    engine = DirectMlOcrEngine()
    engine.initialize()

    regions = engine.recognize_regions(image=object(), regions=[])

    assert regions == []


def test_recognize_regions_uses_rapidocr_and_maps_geometry(monkeypatch):
    import numpy as np

    class _FakeRecResult:
        def __init__(self, txts, scores):
            self.txts = txts
            self.scores = scores

    class _FakeRapidOCR:
        def recognize_txt(self, crops):
            return _FakeRecResult(txts=("hello directml",), scores=(0.95,))

    monkeypatch.setattr(module, "_construct_rapidocr", lambda **_: _FakeRapidOCR())
    monkeypatch.setattr(module, "_crop_polygon_region", lambda img, poly: img)

    engine = DirectMlOcrEngine(language="en")
    engine.initialize()

    dummy_image = np.zeros((50, 50, 3), dtype=np.uint8)
    polys = [((1.0, 2.0), (10.0, 2.0), (10.0, 20.0), (1.0, 20.0))]
    regions = engine.recognize_regions(image=dummy_image, regions=polys)

    assert len(regions) == 1
    assert regions[0].text == "hello directml"
    assert regions[0].confidence == 0.95
    assert regions[0].language == "en"
    assert regions[0].geometry == ((1.0, 2.0), (10.0, 2.0), (10.0, 20.0), (1.0, 20.0))

    engine.shutdown()


def test_runtime_info_reports_directml_backend():
    engine = DirectMlOcrEngine()

    info = engine.runtime_info()

    assert info.engine_name == "RapidOCR"
    assert info.backend == "directml"
    assert info.backend_version == "onnxruntime-directml"
