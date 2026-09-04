from __future__ import annotations

import importlib.util
import sys

from glyphcue.adapters.directml_ocr_engine import DirectMlOcrEngine
from glyphcue.adapters.ocr_engine import OcrEngine
from glyphcue.adapters.ocr_types import OcrInitializationError
from glyphcue.adapters.paddleocr_engine import PaddleOcrEngine


def directml_platform_supported() -> bool:
    """Cheap, non-importing preflight: DirectML is Windows-only by
    construction (ONNX Runtime's DirectML execution provider only exists on
    Windows/DX12) and only worth attempting if the opt-in [directml] extra's
    `rapidocr` package is actually installed. Never imports rapidocr/onnxruntime
    itself -- that cost (and any real provider-initialization failure) is
    paid only inside `_directml_probe_succeeds`, and only when a caller has
    already opted in."""
    return sys.platform == "win32" and importlib.util.find_spec("rapidocr") is not None


def _directml_probe_succeeds(language: str) -> bool:
    """Real initialization probe: package presence alone does not prove the
    DirectML execution provider actually initializes on this machine (e.g. a
    missing/older GPU driver). Discarded either way -- the caller gets a
    fresh, uninitialized engine of whichever backend wins, so the normal
    Paddle path pays no extra cost and behaves exactly as before this
    module existed."""
    probe = DirectMlOcrEngine(language)
    try:
        probe.initialize()
    except OcrInitializationError:
        return False
    finally:
        probe.shutdown()
    return True


def create_ocr_engine(language: str, *, prefer_directml: bool = False) -> OcrEngine:
    """Choose which OcrEngine implementation a caller should construct.

    PaddleOcrEngine (P2 recognition-only) remains the default and the
    automatic fallback in every case: non-Windows platforms, the
    [directml] extra not installed, or the DirectML execution provider
    failing to initialize on this machine. `prefer_directml=True` is the
    explicit opt-in this gates -- omitting it (the default) never attempts
    DirectML at all, so existing callers are unaffected.

    Returns an uninitialized engine, matching every existing call site's
    convention of calling engine.initialize() itself inside the job.
    """
    if prefer_directml and directml_platform_supported() and _directml_probe_succeeds(language):
        return DirectMlOcrEngine(language)
    return PaddleOcrEngine(language)
