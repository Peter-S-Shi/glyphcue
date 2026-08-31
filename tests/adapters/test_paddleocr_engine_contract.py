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
