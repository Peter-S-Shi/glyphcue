"""Pure-Python PaddleOcrEngine contract tests.

Deliberately NOT gated by pytest.importorskip("paddleocr"): these only
exercise language-code mapping, result-shape conversion, and version
reporting, all monkeypatched at the `_construct_paddleocr` seam, so they
never import the real paddleocr/paddlepaddle packages. This lets normal
Python 3.12 CI (which does not install the ~590MB [ocr] extra) still
cover the normalized contract. Tests that exercise the real vendor
runtime live in test_paddleocr_engine.py, gated by importorskip.
"""

import pytest

import glyphcue.adapters.paddleocr_engine as module
from glyphcue.adapters.paddleocr_engine import PaddleOcrEngine


class _FakePaddleModel:
    def __init__(self, result):
        self._result = result

    def predict(self, image):
        return self._result


def test_constructing_with_an_unsupported_language_raises_value_error():
    with pytest.raises(ValueError):
        PaddleOcrEngine(language="fr")


def test_supported_languages_returns_canonical_glyphcue_codes_only():
    engine = PaddleOcrEngine()

    languages = engine.supported_languages()

    assert languages == ("en", "zh", "ja")
    assert "ch" not in languages
    assert "japan" not in languages


@pytest.mark.parametrize(
    "canonical, paddle_code",
    [("en", "en"), ("zh", "ch"), ("ja", "japan")],
)
def test_canonical_language_is_mapped_to_the_paddle_code_at_construction(
    monkeypatch, canonical, paddle_code
):
    captured = {}

    def _fake_construct(*, language):
        captured["language"] = language
        return _FakePaddleModel([])

    monkeypatch.setattr(module, "_construct_paddleocr", _fake_construct)
    engine = PaddleOcrEngine(language=canonical)

    engine.initialize()

    assert captured["language"] == paddle_code


def test_recognize_reports_the_canonical_language_not_the_paddle_code(monkeypatch):
    monkeypatch.setattr(
        module,
        "_construct_paddleocr",
        lambda **_: _FakePaddleModel([{"rec_texts": ["你好"], "rec_scores": [0.99]}]),
    )
    engine = PaddleOcrEngine(language="zh")
    engine.initialize()

    regions = engine.recognize(image=object())

    assert regions[0].language == "zh"


def test_recognize_converts_paddle_polygons_to_vendor_neutral_geometry(monkeypatch):
    monkeypatch.setattr(
        module,
        "_construct_paddleocr",
        lambda **_: _FakePaddleModel(
            [
                {
                    "rec_texts": ["hi"],
                    "rec_scores": [0.9],
                    "rec_polys": [[[1, 2], [10, 2], [10, 20], [1, 20]]],
                }
            ]
        ),
    )
    engine = PaddleOcrEngine()
    engine.initialize()

    regions = engine.recognize(image=object())

    assert regions[0].geometry == ((1.0, 2.0), (10.0, 2.0), (10.0, 20.0), (1.0, 20.0))


def test_recognize_leaves_geometry_none_when_paddle_reports_no_polygons(monkeypatch):
    monkeypatch.setattr(
        module,
        "_construct_paddleocr",
        lambda **_: _FakePaddleModel([{"rec_texts": ["hi"], "rec_scores": [0.9]}]),
    )
    engine = PaddleOcrEngine()
    engine.initialize()

    regions = engine.recognize(image=object())

    assert regions[0].geometry is None


def test_runtime_info_reports_paddleocr_and_paddlepaddle_versions_distinctly(monkeypatch):
    monkeypatch.setattr(module, "_paddleocr_version", lambda: "3.7.0")
    monkeypatch.setattr(module, "_paddlepaddle_version", lambda: "3.3.1")
    engine = PaddleOcrEngine()

    info = engine.runtime_info()

    assert info.engine_name == "PaddleOCR"
    assert info.version == "3.7.0"
    assert info.backend_version == "3.3.1"


def test_paddleocr_engine_satisfies_region_ocr_engine_protocol():
    from glyphcue.adapters.ocr_engine import RegionOcrEngine

    engine = PaddleOcrEngine()
    assert isinstance(engine, RegionOcrEngine)


def test_recognize_regions_before_initialize_raises_a_normalized_error():
    engine = PaddleOcrEngine()

    with pytest.raises(module.OcrRecognitionError):
        engine.recognize_regions(image=object(), regions=[[0, 0], [10, 0], [10, 5], [0, 5]])


def test_recognize_regions_with_empty_regions_returns_empty_list_immediately():
    engine = PaddleOcrEngine()
    engine.initialize()

    regions = engine.recognize_regions(image=object(), regions=[])

    assert regions == []


def test_recognize_regions_uses_underlying_recognizer_and_maps_geometry(monkeypatch):
    class _FakePipeline:
        def __init__(self):
            self.text_rec_score_thresh = 0.5
            self.called_det = False

        def _sort_boxes(self, boxes):
            return boxes

        def _crop_by_polys(self, img, boxes):
            import numpy as np
            for _ in boxes:
                yield np.ones((10, 20, 3), dtype=np.uint8)

        def text_rec_model(self, crops, return_word_box=False):
            return [{"rec_text": "hello region", "rec_score": 0.92}]

    class _FakeEngineWithPipeline:
        def __init__(self):
            self.paddlex_pipeline = _FakePipeline()

    monkeypatch.setattr(module, "_construct_paddleocr", lambda **_: _FakeEngineWithPipeline())
    engine = PaddleOcrEngine(language="en")
    engine.initialize()

    polys = [((1.0, 2.0), (10.0, 2.0), (10.0, 20.0), (1.0, 20.0))]
    regions = engine.recognize_regions(image=object(), regions=polys)

    assert len(regions) == 1
    assert regions[0].text == "hello region"
    assert regions[0].confidence == 0.92
    assert regions[0].language == "en"
    assert regions[0].geometry == ((1.0, 2.0), (10.0, 2.0), (10.0, 20.0), (1.0, 20.0))

