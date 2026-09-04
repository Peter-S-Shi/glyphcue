"""Pure-Python backend-selection contract tests.

No real rapidocr/paddleocr import required: directml_platform_supported and
_directml_probe_succeeds are monkeypatched at their own seams here, the same
way the DirectMlOcrEngine/PaddleOcrEngine contract tests isolate their own
vendor constructors.
"""

from __future__ import annotations

import glyphcue.adapters.ocr_engine_selection as module
from glyphcue.adapters.directml_ocr_engine import DirectMlOcrEngine
from glyphcue.adapters.ocr_engine_selection import create_ocr_engine
from glyphcue.adapters.paddleocr_engine import PaddleOcrEngine


def test_default_call_never_attempts_directml_even_when_supported(monkeypatch):
    probed = {"called": False}

    def _probe(*a, **k):
        probed["called"] = True
        return True

    monkeypatch.setattr(module, "directml_platform_supported", lambda: True)
    monkeypatch.setattr(module, "_directml_probe_succeeds", _probe)

    engine = create_ocr_engine("en")

    assert isinstance(engine, PaddleOcrEngine)
    assert probed["called"] is False


def test_prefer_directml_falls_back_to_paddle_on_unsupported_platform(monkeypatch):
    monkeypatch.setattr(module, "directml_platform_supported", lambda: False)
    monkeypatch.setattr(
        module,
        "_directml_probe_succeeds",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not probe when platform check fails")),
    )

    engine = create_ocr_engine("en", prefer_directml=True)

    assert isinstance(engine, PaddleOcrEngine)


def test_prefer_directml_falls_back_to_paddle_when_provider_init_fails(monkeypatch):
    monkeypatch.setattr(module, "directml_platform_supported", lambda: True)
    monkeypatch.setattr(module, "_directml_probe_succeeds", lambda *a, **k: False)

    engine = create_ocr_engine("en", prefer_directml=True)

    assert isinstance(engine, PaddleOcrEngine)


def test_prefer_directml_returns_directml_when_platform_and_provider_succeed(monkeypatch):
    monkeypatch.setattr(module, "directml_platform_supported", lambda: True)
    monkeypatch.setattr(module, "_directml_probe_succeeds", lambda *a, **k: True)

    engine = create_ocr_engine("en", prefer_directml=True)

    assert isinstance(engine, DirectMlOcrEngine)


def test_directml_platform_supported_is_false_on_non_windows(monkeypatch):
    monkeypatch.setattr(module.sys, "platform", "linux")

    assert module.directml_platform_supported() is False


def test_directml_platform_supported_is_false_when_package_missing(monkeypatch):
    monkeypatch.setattr(module.sys, "platform", "win32")
    monkeypatch.setattr(module.importlib.util, "find_spec", lambda name: None)

    assert module.directml_platform_supported() is False


def test_directml_probe_returns_false_on_initialization_error(monkeypatch):
    from glyphcue.adapters.ocr_types import OcrInitializationError

    def _boom(**kwargs):
        raise RuntimeError("no DX12-capable adapter")

    import glyphcue.adapters.directml_ocr_engine as directml_module

    monkeypatch.setattr(directml_module, "_construct_rapidocr", _boom)

    assert module._directml_probe_succeeds("en") is False
