"""DevQA-only, fail-closed DirectML verification for GlyphCue.

Not part of the shipped product. Run via Launch-GlyphCue-DirectML-DevQA.bat
before it starts the normal `python -m glyphcue` product UI.

Purpose: prove -- deterministically, with no silent fallback -- that
`glyphcue.adapters.ocr_engine_selection.create_ocr_engine` and
`glyphcue.adapters.text_detector_selection.create_text_detector`, run with
`prefer_directml=True` in *this* interpreter, actually construct
`DirectMlOcrEngine`/`DirectMlTextDetector` and that the underlying ONNX
Runtime sessions report `DmlExecutionProvider` as an active provider.

Exits 0 only when every check below passes. Exits 1 and prints the first
failing check otherwise -- this script never falls back to Paddle and
reports success; a failure here means the DevQA entrypoint refuses to
launch the product at all (see the .bat wrapper).

Does not touch product code, Architecture B, or OCR quality logic. This is
diagnostic instrumentation only.
"""

from __future__ import annotations

import sys


def _fail(message: str) -> None:
    print(f"[DevQA DirectML preflight] FAIL: {message}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    from glyphcue.adapters.ocr_engine_selection import directml_platform_supported
    from glyphcue.adapters.text_detector_selection import (
        _directml_detector_probe_succeeds,
        directml_detector_platform_supported,
    )

    if not directml_platform_supported():
        _fail(
            "directml_platform_supported() is False -- either not win32, "
            "or the 'rapidocr' package is not importable in this interpreter "
            f"({sys.executable}). Install the [directml] extra into this "
            "venv: pip install -e \".[ocr,directml]\"."
        )

    from glyphcue.adapters.directml_ocr_engine import DirectMlOcrEngine

    engine = DirectMlOcrEngine("en")
    try:
        engine.initialize()
    except Exception as exc:  # noqa: BLE001 -- report exact cause, then fail closed
        _fail(f"DirectMlOcrEngine.initialize() raised: {exc!r}")

    rapid = engine._engine
    if rapid is None:
        _fail("DirectMlOcrEngine initialized but ._engine is None.")

    det_sess = getattr(getattr(rapid, "text_det", None), "session", None)
    rec_sess = getattr(getattr(rapid, "text_rec", None), "session", None)
    det_raw = getattr(det_sess, "session", None)
    rec_raw = getattr(rec_sess, "session", None)

    if det_raw is None or rec_raw is None:
        _fail(
            "Could not drill to raw onnxruntime.InferenceSession via "
            "engine._engine.text_det/text_rec.session.session -- RapidOCR's "
            "internal shape may have changed."
        )

    det_providers = det_raw.get_providers()
    rec_providers = rec_raw.get_providers()
    engine.shutdown()

    if "DmlExecutionProvider" not in det_providers:
        _fail(f"OCR detector-side session providers = {det_providers!r}, no DmlExecutionProvider.")
    if "DmlExecutionProvider" not in rec_providers:
        _fail(f"OCR recognizer session providers = {rec_providers!r}, no DmlExecutionProvider.")

    print(f"[DevQA DirectML preflight] OK: DirectMlOcrEngine active, det providers={det_providers}, rec providers={rec_providers}")

    if not directml_detector_platform_supported():
        _fail(
            "directml_detector_platform_supported() is False -- missing one "
            "of onnxruntime/cv2/pyclipper in this interpreter."
        )

    if not _directml_detector_probe_succeeds():
        _fail("DirectMlTextDetector real init+run probe failed (see text_detector_selection._directml_detector_probe_succeeds).")

    from glyphcue.adapters.directml_text_detector import DirectMlTextDetector

    detector = DirectMlTextDetector()
    detector.initialize()
    det_providers2 = detector._detector.sess.get_providers()
    detector.shutdown()

    if "DmlExecutionProvider" not in det_providers2:
        _fail(f"DirectMlTextDetector session providers = {det_providers2!r}, no DmlExecutionProvider.")

    print(f"[DevQA DirectML preflight] OK: DirectMlTextDetector active, providers={det_providers2}")
    print("[DevQA DirectML preflight] PASS: DirectML OCR engine + text detector both confirmed active with DmlExecutionProvider.")


if __name__ == "__main__":
    main()
