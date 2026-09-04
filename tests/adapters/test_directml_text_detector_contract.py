"""Pure-Python DirectMlTextDetector contract and geometry parity guard tests.

Deliberately NOT gated by pytest.importorskip("rapidocr") or requiring GPU:
these exercise initialization, contract compliance, error handling,
polygon vertex canonical ordering, and output geometry shape, all monkeypatched
at the constructor seam. This allows Linux and GitHub CI to run without
the Windows-only [directml] extra.
"""

from __future__ import annotations

import numpy as np
import pytest

import glyphcue.adapters.directml_text_detector as detector_module
from glyphcue.adapters.directml_text_detector import (
    DirectMlTextDetector,
    _order_box_points,
    _resolve_medium_detector_model_path,
)


def test_order_box_points_produces_canonical_clockwise_order():
    # Vertices returned from cv2.boxPoints
    points = np.array([
        [100.0, 40.0],
        [10.0, 20.0],
        [10.0, 40.0],
        [100.0, 20.0],
    ], dtype=np.float32)

    ordered = _order_box_points(points)

    assert ordered[0] == [10.0, 20.0]   # top-left
    assert ordered[1] == [100.0, 20.0]  # top-right
    assert ordered[2] == [100.0, 40.0]  # bottom-right
    assert ordered[3] == [10.0, 40.0]   # bottom-left


def test_resolve_medium_detector_model_path_raises_when_not_found(monkeypatch, tmp_path):
    monkeypatch.setattr(detector_module, "_DEFAULT_MODELS_DIR", tmp_path / "nonexistent")
    monkeypatch.setattr(detector_module.Path, "home", lambda: tmp_path)

    with pytest.raises(RuntimeError, match="PP-OCRv6_det_medium.onnx not found"):
        _resolve_medium_detector_model_path()


def test_call_before_initialize_raises_runtime_error():
    detector = DirectMlTextDetector()
    dummy = np.zeros((100, 200, 3), dtype=np.uint8)

    with pytest.raises(RuntimeError, match="initialize.*must be called first"):
        detector(dummy)


def test_initialize_failure_raises_runtime_error(monkeypatch):
    def _boom(**kwargs):
        raise RuntimeError("DirectML provider initialization failed")

    monkeypatch.setattr(detector_module, "_construct_detector_backend", _boom)
    detector = DirectMlTextDetector()

    with pytest.raises(RuntimeError, match="DirectML provider initialization failed"):
        detector.initialize()


def test_call_with_empty_boxes_returns_empty_list(monkeypatch):
    class FakeDetector:
        def __call__(self, img):
            return []

    monkeypatch.setattr(detector_module, "_construct_detector_backend", lambda **_: FakeDetector())
    detector = DirectMlTextDetector()
    detector.initialize()

    dummy = np.zeros((100, 200, 3), dtype=np.uint8)
    polys = detector(dummy)

    assert polys == []
    detector.shutdown()


def test_call_with_detected_boxes_returns_list_of_4x2_ndarrays(monkeypatch):
    boxes = [
        np.array([[10.0, 20.0], [50.0, 20.0], [50.0, 40.0], [10.0, 40.0]], dtype=np.float32),
        np.array([[60.0, 20.0], [100.0, 20.0], [100.0, 40.0], [60.0, 40.0]], dtype=np.float32),
    ]

    class FakeDetector:
        def __call__(self, img):
            return boxes

    monkeypatch.setattr(detector_module, "_construct_detector_backend", lambda **_: FakeDetector())
    detector = DirectMlTextDetector(limit_side_len=640)
    detector.initialize()

    dummy = np.zeros((100, 200, 3), dtype=np.uint8)
    polys = detector(dummy)

    assert len(polys) == 2
    for p in polys:
        assert isinstance(p, np.ndarray)
        assert p.shape == (4, 2)
    assert np.allclose(polys[0][0], [10.0, 20.0])
    assert np.allclose(polys[1][2], [100.0, 40.0])

    detector.shutdown()


def test_initialize_raises_when_dml_provider_is_not_actually_active(monkeypatch):
    # ONNX Runtime does not raise when the requested DmlExecutionProvider
    # is unavailable -- InferenceSession silently substitutes
    # CPUExecutionProvider instead. Package/platform presence alone (what
    # directml_detector_platform_supported checks) is therefore not proof
    # DirectML actually got selected; only the initialized session's own
    # get_providers() is. A session that silently fell back to CPU must
    # be treated as a failed DirectML initialization, not a quiet success.
    ort = pytest.importorskip("onnxruntime")

    class _FakeCpuOnlySession:
        def get_providers(self):
            return ["CPUExecutionProvider"]

        def get_inputs(self):
            return [type("Input", (), {"name": "x"})()]

    monkeypatch.setattr(ort, "InferenceSession", lambda *a, **k: _FakeCpuOnlySession())
    monkeypatch.setattr(
        detector_module, "_resolve_medium_detector_model_path", lambda *a, **k: "fake.onnx"
    )

    with pytest.raises(RuntimeError, match="DmlExecutionProvider"):
        detector_module._ExactPaddleDirectMlDetectorBackend(model_path="fake.onnx").initialize()


def test_initialize_succeeds_when_dml_provider_is_genuinely_active(monkeypatch):
    ort = pytest.importorskip("onnxruntime")

    class _FakeDmlSession:
        def get_providers(self):
            return ["DmlExecutionProvider", "CPUExecutionProvider"]

        def get_inputs(self):
            return [type("Input", (), {"name": "x"})()]

    monkeypatch.setattr(ort, "InferenceSession", lambda *a, **k: _FakeDmlSession())
    monkeypatch.setattr(
        detector_module, "_resolve_medium_detector_model_path", lambda *a, **k: "fake.onnx"
    )

    backend = detector_module._ExactPaddleDirectMlDetectorBackend(model_path="fake.onnx")
    backend.initialize()  # must not raise

    assert backend.sess.get_providers() == ["DmlExecutionProvider", "CPUExecutionProvider"]


def test_shutdown_cleans_up_detector(monkeypatch):
    class FakeDetector:
        def shutdown(self):
            pass

    monkeypatch.setattr(detector_module, "_construct_detector_backend", lambda **_: FakeDetector())
    detector = DirectMlTextDetector()
    detector.initialize()
    assert detector._detector is not None

    detector.shutdown()
    assert detector._detector is None

    dummy = np.zeros((100, 200, 3), dtype=np.uint8)
    with pytest.raises(RuntimeError, match="initialize.*must be called first"):
        detector(dummy)
