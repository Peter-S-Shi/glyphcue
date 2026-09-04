"""M11 Research Gate -- occupancy-normalized signature distance.

Research-only: nothing in the production OCR path imports this yet.
"""

import numpy as np
import pytest

from glyphcue.application.beta_stroke_structural import beta_s_signature
from glyphcue.application.detector_assisted_signature import (
    CANONICAL_BAND_HEIGHT,
    CANONICAL_BAND_WIDTH,
    MAX_LINES,
)
from glyphcue.application.occupancy_normalized_distance import (
    occupancy_normalized_distance,
    occupied_bands,
)
from glyphcue.application.visual_state_sampling import signature_distance

_CANVAS = (MAX_LINES * CANONICAL_BAND_HEIGHT, CANONICAL_BAND_WIDTH)


def _poly(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


_LINE_ONE = _poly(50, 18, 820, 46)
_LINE_TWO = _poly(50, 60, 820, 88)
_GLYPHS = list(range(60, 800, 11))
_OTHER_GLYPHS = list(range(60, 800, 17))


def _two_line_frame(glyph_columns) -> np.ndarray:
    frame = np.full((100, 900, 3), 235, dtype=np.uint8)
    for column in glyph_columns:
        frame[20:44, column : column + 3] = 25
        frame[62:86, column : column + 3] = 25
    return frame


def _canvas_with(bands: dict[int, np.ndarray]) -> np.ndarray:
    canvas = np.zeros(_CANVAS, dtype=bool)
    for index, band in bands.items():
        top = index * CANONICAL_BAND_HEIGHT
        canvas[top : top + CANONICAL_BAND_HEIGHT, :] = band
    return canvas


def _band(fill: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.random((CANONICAL_BAND_HEIGHT, CANONICAL_BAND_WIDTH)) < fill


def test_identical_signatures_are_zero_apart():
    signature = _canvas_with({0: _band(0.2, 1)})

    assert occupancy_normalized_distance(signature, signature) == 0.0


def test_two_fully_blank_signatures_are_zero_apart():
    blank = np.zeros(_CANVAS, dtype=bool)

    assert occupancy_normalized_distance(blank, blank) == 0.0


def test_it_is_symmetric():
    a = _canvas_with({0: _band(0.2, 1)})
    b = _canvas_with({0: _band(0.2, 2)})

    assert occupancy_normalized_distance(a, b) == occupancy_normalized_distance(b, a)


def test_mismatched_shapes_are_maximally_distant():
    a = np.zeros((5, 5), dtype=bool)
    b = np.zeros((6, 6), dtype=bool)

    assert occupancy_normalized_distance(a, b) == 1.0


def test_occupied_bands_reports_which_bands_carry_ink():
    signature = _canvas_with({0: _band(0.2, 1), 2: _band(0.2, 2)})

    assert occupied_bands(signature) == [True, False, True, False]


def test_a_band_present_in_only_one_signature_still_contributes_mismatch():
    """The normalization must not degenerate into comparing the
    intersection: gaining or losing a caption LINE is real evidence that
    the subtitle state changed, and has to survive."""
    shared = _band(0.2, 1)
    one_line = _canvas_with({0: shared})
    two_lines = _canvas_with({0: shared, 1: _band(0.2, 2)})

    distance = occupancy_normalized_distance(one_line, two_lines)

    # Band 0 agrees perfectly; band 1 is entirely one-sided, so every
    # ink cell in it is a mismatch and the union covers both bands.
    expected = _band(0.2, 2).sum() / (2 * CANONICAL_BAND_HEIGHT * CANONICAL_BAND_WIDTH)
    assert distance == pytest.approx(expected)
    assert distance > 0


def test_the_distance_no_longer_scales_with_how_many_lines_were_detected():
    """The defect this metric exists to remove (see the characterization
    in test_beta_stroke_structural): the SAME per-line content change
    measured across one detected line and across two must give the same
    answer. Under the production distance the two-line case reads twice
    as far, purely because the fixed canvas has one fewer empty band to
    dilute it with."""
    a_one = beta_s_signature(_two_line_frame(_GLYPHS), [_LINE_ONE])
    b_one = beta_s_signature(_two_line_frame(_OTHER_GLYPHS), [_LINE_ONE])
    a_two = beta_s_signature(_two_line_frame(_GLYPHS), [_LINE_ONE, _LINE_TWO])
    b_two = beta_s_signature(_two_line_frame(_OTHER_GLYPHS), [_LINE_ONE, _LINE_TWO])

    one_line = occupancy_normalized_distance(a_one, b_one)
    two_lines = occupancy_normalized_distance(a_two, b_two)

    assert one_line > 0
    assert two_lines == pytest.approx(one_line, rel=0.05)

    # ...which is exactly what the production distance does not do.
    assert signature_distance(a_two, b_two) == pytest.approx(
        2 * signature_distance(a_one, b_one), rel=0.05
    )


def test_it_agrees_with_the_production_distance_when_the_canvas_is_full():
    """Nothing else changes: with every band occupied the normalization
    denominator is the whole canvas and the two metrics coincide."""
    a = _canvas_with({index: _band(0.2, index) for index in range(MAX_LINES)})
    b = _canvas_with({index: _band(0.2, index + 10) for index in range(MAX_LINES)})

    assert occupancy_normalized_distance(a, b) == pytest.approx(signature_distance(a, b))
