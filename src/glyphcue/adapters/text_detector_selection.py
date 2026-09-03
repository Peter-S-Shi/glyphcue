"""Selection and safe fallback for text detection backends.

Provides runtime detection selection between the shipped PaddlePaddle CPU
detector (default everywhere) and the opt-in Windows DirectML GPU detector.
Safe fallback to Paddle CPU occurs on any unsupported platform, missing package,
or runtime initialization failure.
"""

from __future__ import annotations

import importlib.util
import sys

import numpy as np

from glyphcue.adapters.directml_text_detector import DirectMlTextDetector
from glyphcue.adapters.paddleocr_text_detector import PaddleOcrTextDetector
from glyphcue.application.hybrid_evidence_job import TextDetector


def directml_detector_platform_supported() -> bool:
    """Cheap, non-importing preflight: DirectML is Windows-only by
    construction (ONNX Runtime DirectML provider only exists on Windows/DX12)
    and only worth attempting if onnxruntime, cv2, and pyclipper are all installed.
    Never imports heavy native packages during preflight."""
    if sys.platform != "win32":
        return False
    return (
        importlib.util.find_spec("onnxruntime") is not None
        and importlib.util.find_spec("cv2") is not None
        and importlib.util.find_spec("pyclipper") is not None
    )


def _directml_detector_probe_succeeds() -> bool:
    """Real initialization and execution probe: package presence alone does not
    prove the DirectML execution provider actually initializes on this machine
    (e.g. a missing/older GPU driver or missing ONNX model artifact).
    Executes a lightweight synthetic frame through the full pre/post-process
    pipeline. Discarded either way -- the caller gets a fresh, uninitialized
    detector of whichever backend wins."""
    probe = DirectMlTextDetector()
    try:
        probe.initialize()
        probe(np.zeros((32, 32, 3), dtype=np.uint8))
    except Exception:
        return False
    finally:
        probe.shutdown()
    return True


def create_text_detector(*, prefer_directml: bool = False) -> TextDetector:
    """Choose which TextDetector implementation a caller should construct.

    PaddleOcrTextDetector (PaddlePaddle CPU) remains the default and the
    automatic fallback in every case: non-Windows platforms, missing packages,
    missing model artifact, or DirectML provider failing to initialize.
    `prefer_directml=True` is the explicit opt-in this gates -- omitting it
    (the default) never attempts DirectML at all, so existing callers are
    unaffected.

    Returns an uninitialized detector, matching every existing call site's
    convention of calling detector.initialize() itself inside the job.
    """
    if (
        prefer_directml
        and directml_detector_platform_supported()
        and _directml_detector_probe_succeeds()
    ):
        return DirectMlTextDetector()
    return PaddleOcrTextDetector()
