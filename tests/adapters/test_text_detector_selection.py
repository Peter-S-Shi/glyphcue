"""Targeted TDD tests for text detector selection and fallback.

Deliberately pure-Python unit tests -- runnable on any platform and in
CI without requiring GPU hardware or the [directml] extra.
"""

from __future__ import annotations

import sys
import pytest

import glyphcue.adapters.text_detector_selection as sel
from glyphcue.adapters.paddleocr_text_detector import PaddleOcrTextDetector


def test_create_text_detector_defaults_to_paddle_cpu():
    detector = sel.create_text_detector()
    assert isinstance(detector, PaddleOcrTextDetector)


def test_create_text_detector_prefer_false_returns_paddle_cpu():
    detector = sel.create_text_detector(prefer_directml=False)
    assert isinstance(detector, PaddleOcrTextDetector)


def test_create_text_detector_prefer_true_falls_back_on_non_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sel, "directml_detector_platform_supported", lambda: False)

    detector = sel.create_text_detector(prefer_directml=True)
    assert isinstance(detector, PaddleOcrTextDetector)


def test_create_text_detector_prefer_true_falls_back_when_packages_missing(monkeypatch):
    monkeypatch.setattr(sel, "directml_detector_platform_supported", lambda: False)

    detector = sel.create_text_detector(prefer_directml=True)
    assert isinstance(detector, PaddleOcrTextDetector)


def test_create_text_detector_prefer_true_falls_back_when_probe_fails(monkeypatch):
    monkeypatch.setattr(sel, "directml_detector_platform_supported", lambda: True)
    monkeypatch.setattr(sel, "_directml_detector_probe_succeeds", lambda: False)

    detector = sel.create_text_detector(prefer_directml=True)
    assert isinstance(detector, PaddleOcrTextDetector)


def test_create_text_detector_prefer_true_returns_directml_when_probe_succeeds(monkeypatch):
    class FakeDirectMlDetector:
        pass

    monkeypatch.setattr(sel, "directml_detector_platform_supported", lambda: True)
    monkeypatch.setattr(sel, "_directml_detector_probe_succeeds", lambda: True)
    monkeypatch.setattr(sel, "DirectMlTextDetector", FakeDirectMlDetector)

    detector = sel.create_text_detector(prefer_directml=True)
    assert isinstance(detector, FakeDirectMlDetector)
