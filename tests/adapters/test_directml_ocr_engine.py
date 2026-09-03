"""Real-runtime DirectMlOcrEngine tests: require the Windows-only [directml]
extra (rapidocr + onnxruntime-directml) actually installed, and only run on
Windows -- DirectML has no execution provider anywhere else. Both are opt-in
in CI; a machine without them skips this whole file, the same way
test_paddleocr_engine.py skips without paddleocr installed.

This module confirms the DirectML execution provider is genuinely selected
(not silently falling back to onnxruntime's CPU provider), not merely that
RapidOCR constructs without error -- provider-list membership doesn't prove
GPU execution on its own (see docs/adr/0001-ocr-runtime-selection.md's
Milestone 11 addendum), but it is the right lightweight regression check for
routine runs; the one-time rigorous ORT-profiling proof lives in the private
Phase 0B evidence referenced there.
"""

from __future__ import annotations

import sys

import pytest

if sys.platform != "win32":
    pytest.skip("DirectML has no execution provider outside Windows", allow_module_level=True)

pytest.importorskip("rapidocr", reason="rapidocr is the opt-in, Windows-only [directml] extra")

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from glyphcue.adapters.directml_ocr_engine import DirectMlOcrEngine
from glyphcue.adapters.ocr_engine import OcrEngine, RegionOcrEngine
from glyphcue.adapters.ocr_types import OcrRecognitionError


def _text_image(text: str) -> np.ndarray:
    image = Image.new("RGB", (300, 50), color=(20, 20, 20))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("arial.ttf", 24)
    draw.text((8, 10), text, font=font, fill=(255, 255, 255))
    return np.array(image)


def test_directml_ocr_engine_satisfies_ocr_engine_and_region_ocr_engine_protocols():
    engine: OcrEngine = DirectMlOcrEngine()

    assert isinstance(engine, OcrEngine)
    assert isinstance(engine, RegionOcrEngine)


def test_recognize_returns_normalized_text_regions_and_selects_the_dml_provider():
    engine = DirectMlOcrEngine()
    engine.initialize()
    try:
        session = engine._engine.text_rec.session.session
        providers = session.get_providers()
        assert "DmlExecutionProvider" in providers, (
            f"DirectML provider not registered; got {providers}. Provider-list "
            "membership alone doesn't prove GPU execution (see ADR 0001's "
            "Milestone 11 addendum) but its absence does prove DirectML isn't "
            "even being attempted."
        )

        regions = engine.recognize(_text_image("Hello world"))
    finally:
        engine.shutdown()

    assert len(regions) == 1
    assert regions[0].text.strip() != ""
    assert 0.0 < regions[0].confidence <= 1.0
    assert regions[0].language == "en"


def test_recognize_regions_matches_full_recognize_and_performs_zero_detection():
    image = Image.new("RGB", (400, 140), color=(20, 20, 20))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("arial.ttf", 24)
    draw.text((10, 10), "First Line GlyphCue", font=font, fill=(255, 255, 255))
    draw.text((10, 55), "Second Line World", font=font, fill=(255, 255, 255))
    img_arr = np.array(image)

    engine = DirectMlOcrEngine(language="en")
    engine.initialize()
    try:
        full_regions = engine.recognize(img_arr)
        assert len(full_regions) == 2

        polygons = [r.geometry for r in full_regions]
        assert all(poly is not None for poly in polygons)

        original_text_det = engine._engine.text_det

        def _forbidden_det(*a, **k):
            raise AssertionError("text_det was called during recognize_regions")

        engine._engine.text_det = _forbidden_det
        try:
            rec_regions = engine.recognize_regions(img_arr, polygons)
        finally:
            engine._engine.text_det = original_text_det

        assert len(rec_regions) == len(full_regions)
        for full, rec in zip(full_regions, rec_regions):
            assert rec.text == full.text
    finally:
        engine.shutdown()


def test_recognize_before_initialize_raises_a_normalized_error():
    engine = DirectMlOcrEngine()

    with pytest.raises(OcrRecognitionError):
        engine.recognize(_text_image("anything"))
