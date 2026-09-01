import numpy as np

from glyphcue.application.beta_detector_dry_run import BETA_GROUP_DISTANCE_THRESHOLD
from glyphcue.application.beta_normalized_signature import (
    CANONICAL_HEIGHT,
    CANONICAL_WIDTH,
    MAX_LINES,
    aspect_preserving_coverage_band,
    beta_normalized_signature,
    shift_tolerant_distance,
)


def _poly(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def _line_frame(
    stroke_columns,
    shift: int = 0,
    height: int = 60,
    width: int = 900,
    top: int = 20,
    bottom: int = 44,
) -> np.ndarray:
    """Light background with dark vertical 'strokes' at the given source
    columns -- a font-free stand-in for one caption line."""
    frame = np.full((height, width, 3), 235, dtype=np.uint8)
    for column in stroke_columns:
        x = column + shift
        if 0 <= x < width - 2:
            frame[top:bottom, x : x + 3] = 25
    return frame


# Stroke pitches deliberately chosen NOT to divide evenly into the
# resample grid: a pattern whose period lands exactly on cell boundaries
# would produce artificially clean 0/1 coverage and hide the very
# anti-aliasing behaviour these tests are meant to pin.
_SHORT_LINE = list(range(60, 260, 11))
_LONG_LINE = list(range(60, 800, 11))
_OTHER_LONG_LINE = list(range(60, 800, 17))


def test_band_has_the_declared_canonical_shape():
    frame = _line_frame(_LONG_LINE)

    band = aspect_preserving_coverage_band(frame, (50, 18, 820, 46))

    assert band.shape == (CANONICAL_HEIGHT, CANONICAL_WIDTH)


def test_band_is_a_soft_coverage_map_not_a_hard_binary_mask():
    # Area-averaged coverage is what makes a sub-cell shift move values
    # smoothly instead of flipping whole cells -- the actual cause of
    # Beta's long-line fragmentation.
    band = aspect_preserving_coverage_band(_line_frame(_LONG_LINE), (50, 18, 820, 46))

    assert band.dtype.kind == "f"
    assert band.max() <= 1.0
    assert np.any((band > 0.0) & (band < 1.0))


def test_a_short_line_occupies_less_canvas_width_than_a_long_line():
    # Aspect-preserving normalization + padding keeps line LENGTH as
    # real evidence, instead of stretching every line to full width.
    short = aspect_preserving_coverage_band(_line_frame(_SHORT_LINE), (50, 18, 280, 46))
    long = aspect_preserving_coverage_band(_line_frame(_LONG_LINE), (50, 18, 820, 46))

    short_width = int(np.max(np.flatnonzero(short.any(axis=0))))
    long_width = int(np.max(np.flatnonzero(long.any(axis=0))))
    assert short_width < long_width


def test_same_glyphs_shifted_a_few_pixels_stay_far_below_the_group_threshold():
    # THE Beta-N contract: identical text whose box/ink moved 2-3px must
    # read as the SAME state under the frozen 0.10 grouping threshold.
    reference = beta_normalized_signature(_line_frame(_LONG_LINE), [_poly(50, 18, 820, 46)])

    for shift in (1, 2, 3):
        shifted_frame = _line_frame(_LONG_LINE, shift=shift)
        shifted = beta_normalized_signature(
            shifted_frame, [_poly(50 + shift, 18, 820 + shift, 46)]
        )
        distance = shift_tolerant_distance(reference, shifted)
        assert distance < BETA_GROUP_DISTANCE_THRESHOLD, f"{shift}px shift -> {distance}"


def test_different_glyphs_with_near_identical_geometry_stay_far_above_the_threshold():
    # The sample_b failure the Alpha family died on: two captions with
    # nearly identical box geometry but different text must NOT merge.
    a = beta_normalized_signature(_line_frame(_LONG_LINE), [_poly(50, 18, 820, 46)])
    b = beta_normalized_signature(_line_frame(_OTHER_LONG_LINE), [_poly(50, 18, 820, 46)])

    assert shift_tolerant_distance(a, b) > BETA_GROUP_DISTANCE_THRESHOLD


def test_shift_tolerance_is_bounded_and_does_not_forgive_a_large_displacement():
    # Tolerance must stay small; if it absorbed any displacement it
    # would merge genuinely different states by brute force.
    reference = np.zeros((CANONICAL_HEIGHT, CANONICAL_WIDTH), dtype=np.float64)
    reference[4:12, 10:40] = 1.0
    far = np.zeros_like(reference)
    far[4:12, 200:230] = 1.0

    assert shift_tolerant_distance(reference, far) > 0.9


def test_two_empty_signatures_are_identical():
    empty = np.zeros((CANONICAL_HEIGHT, CANONICAL_WIDTH), dtype=np.float64)

    assert shift_tolerant_distance(empty, empty) == 0.0


def test_an_empty_signature_is_maximally_distant_from_an_inked_one():
    empty = np.zeros((CANONICAL_HEIGHT, CANONICAL_WIDTH), dtype=np.float64)
    inked = np.zeros_like(empty)
    inked[4:12, 10:40] = 1.0

    assert shift_tolerant_distance(empty, inked) == 1.0


def test_signature_stacks_one_band_per_detected_line():
    frame = _line_frame(_LONG_LINE, height=120)
    polygons = [_poly(50, 18, 820, 46), _poly(50, 60, 820, 88)]

    signature = beta_normalized_signature(frame, polygons)

    assert signature.shape == (MAX_LINES * CANONICAL_HEIGHT, CANONICAL_WIDTH)


def test_signature_is_empty_when_the_detector_reports_no_text():
    signature = beta_normalized_signature(_line_frame(_LONG_LINE), [])

    assert not signature.any()


def _caption_over_moving_background(background_phase: float) -> np.ndarray:
    """Identical glyphs over a shifting luminance gradient -- a synthetic
    stand-in for a real caption with hands/scene moving BEHIND it, which
    is what sample_b actually contains."""
    height, width = 60, 900
    xs = np.linspace(0, 1, width)[None, :]
    gradient = (170 + 60 * np.sin(2 * np.pi * (xs * 2 + background_phase))).repeat(
        height, axis=0
    )
    frame = np.dstack([gradient] * 3).astype(np.uint8)
    for column in range(60, 800, 11):  # the glyphs never change
        frame[20:44, column : column + 3] = 25
    return frame


def test_characterizes_the_diagnosed_weakness_background_motion_moves_the_signature():
    """CHARACTERIZATION of a KNOWN, UNFIXED weakness -- not a desired
    property.

    Beta-N was built on the premise that within-state fragmentation came
    from 2-3px geometric displacement. Measurement on real frames refuted
    that: the detector box was constant (1267x57), tight ink extent
    varied 0.8%, and the shift search recovered only 0.015 of distance.
    What actually moves the signature is PHOTOMETRIC: the per-patch
    binarization midpoint is derived from the patch's own dynamic range,
    so a background luminance change behind the glyphs reclassifies
    glyph-edge pixels even though the text is pixel-identical.

    This test pins that mechanism so the next round starts from the
    measured cause rather than the refuted premise.
    """
    polygons = [_poly(50, 18, 820, 46)]
    reference = beta_normalized_signature(_caption_over_moving_background(0.0), polygons)
    moved = beta_normalized_signature(_caption_over_moving_background(0.3), polygons)

    distance = shift_tolerant_distance(reference, moved)

    # Identical text, yet already far past the grouping threshold.
    assert distance > BETA_GROUP_DISTANCE_THRESHOLD


def test_sensor_noise_alone_does_not_move_the_signature():
    # Isolates the mechanism above: additive noise WITHOUT a background
    # luminance change is harmless, so the instability is specifically
    # the background-dependent binarization, not general pixel noise.
    rng = np.random.default_rng(7)
    base = _caption_over_moving_background(0.0)
    noisy = np.clip(base.astype(int) + rng.integers(-6, 7, base.shape), 0, 255).astype(
        np.uint8
    )
    polygons = [_poly(50, 18, 820, 46)]

    distance = shift_tolerant_distance(
        beta_normalized_signature(base, polygons),
        beta_normalized_signature(noisy, polygons),
    )

    assert distance < BETA_GROUP_DISTANCE_THRESHOLD
