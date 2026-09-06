from __future__ import annotations

import sys
import types


def _write_frozen_onnx_models(models_dir):
    models_dir.mkdir(parents=True)
    for filename in (
        "PP-OCRv6_det_medium.onnx",
        "PP-OCRv6_rec_small.onnx",
        "ch_ppocr_mobile_v2.0_cls_mobile.onnx",
    ):
        (models_dir / filename).write_bytes(b"model")


def _write_paddle_model_dir(models_dir, dirname):
    model_dir = models_dir / "paddle" / dirname
    model_dir.mkdir(parents=True)
    (model_dir / "inference.json").write_bytes(b"{}")
    (model_dir / "inference.pdiparams").write_bytes(b"pdiparams")


def test_directml_ocr_binds_rapidocr_to_frozen_packaged_onnx_models(
    monkeypatch, tmp_path
):
    models_dir = tmp_path / "models"
    _write_frozen_onnx_models(models_dir)
    captured = {}

    class FakeRapidOCR:
        def __init__(self, *, params):
            captured.update(params)

    monkeypatch.setenv("GLYPHCUE_PACKAGED_MODELS_DIR", str(models_dir))
    monkeypatch.setitem(sys.modules, "rapidocr", types.SimpleNamespace(RapidOCR=FakeRapidOCR))

    from glyphcue.adapters.directml_ocr_engine import _construct_rapidocr

    _construct_rapidocr(use_dml=True)

    assert captured["Det.model_path"] == str(models_dir / "PP-OCRv6_det_medium.onnx")
    assert captured["Rec.model_path"] == str(models_dir / "PP-OCRv6_rec_small.onnx")
    assert captured["Cls.model_path"] == str(models_dir / "ch_ppocr_mobile_v2.0_cls_mobile.onnx")
    assert "PP-OCRv6_det_small.onnx" not in captured["Det.model_path"]


def test_directml_text_detector_binds_to_frozen_packaged_medium_detector(
    monkeypatch, tmp_path
):
    models_dir = tmp_path / "models"
    _write_frozen_onnx_models(models_dir)

    monkeypatch.setenv("GLYPHCUE_PACKAGED_MODELS_DIR", str(models_dir))
    monkeypatch.delenv("GLYPHCUE_DIRECTML_MODELS_DIR", raising=False)
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path / "home")

    from glyphcue.adapters.directml_text_detector import _resolve_medium_detector_model_path

    model_path = _resolve_medium_detector_model_path()

    assert model_path == models_dir / "PP-OCRv6_det_medium.onnx"
    assert ".cache" not in str(model_path)
    assert ".rapidocr" not in str(model_path)


def test_paddle_cpu_engine_binds_pipeline_and_recognizer_to_packaged_models(
    monkeypatch, tmp_path
):
    models_dir = tmp_path / "models"
    _write_paddle_model_dir(models_dir, "PP-OCRv6_medium_det")
    _write_paddle_model_dir(models_dir, "PP-OCRv6_medium_rec")
    captured = {"pipeline": None, "recognizer": None}

    class FakePaddleOCR:
        def __init__(self, **kwargs):
            captured["pipeline"] = kwargs

    class FakeTextRecognition:
        def __init__(self, **kwargs):
            captured["recognizer"] = kwargs

    monkeypatch.setenv("GLYPHCUE_PACKAGED_MODELS_DIR", str(models_dir))
    monkeypatch.setitem(
        sys.modules,
        "paddleocr",
        types.SimpleNamespace(
            PaddleOCR=FakePaddleOCR,
            TextRecognition=FakeTextRecognition,
        ),
    )

    from glyphcue.adapters.paddleocr_engine import (
        _construct_paddleocr,
        _construct_text_recognition,
    )

    _construct_paddleocr(language="en")
    _construct_text_recognition()

    assert captured["pipeline"]["text_detection_model_dir"] == str(
        models_dir / "paddle" / "PP-OCRv6_medium_det"
    )
    assert captured["pipeline"]["text_recognition_model_dir"] == str(
        models_dir / "paddle" / "PP-OCRv6_medium_rec"
    )
    assert captured["recognizer"]["model_dir"] == str(
        models_dir / "paddle" / "PP-OCRv6_medium_rec"
    )


def test_paddle_cpu_text_detector_binds_to_packaged_detector_model(
    monkeypatch, tmp_path
):
    models_dir = tmp_path / "models"
    _write_paddle_model_dir(models_dir, "PP-OCRv6_medium_det")
    captured = {}

    class FakeTextDetection:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setenv("GLYPHCUE_PACKAGED_MODELS_DIR", str(models_dir))
    monkeypatch.setitem(
        sys.modules,
        "paddleocr",
        types.SimpleNamespace(TextDetection=FakeTextDetection),
    )
    monkeypatch.setitem(sys.modules, "numpy", types.SimpleNamespace(asarray=lambda value: value))

    from glyphcue.adapters.paddleocr_text_detector import PaddleOcrTextDetector

    PaddleOcrTextDetector().initialize()

    assert captured["model_dir"] == str(models_dir / "paddle" / "PP-OCRv6_medium_det")
