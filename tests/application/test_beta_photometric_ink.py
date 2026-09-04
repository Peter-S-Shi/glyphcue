import numpy as np

from glyphcue.application.beta_detector_dry_run import BETA_GROUP_DISTANCE_THRESHOLD
from glyphcue.application.beta_photometric_ink import (
    beta_p_signature,
    local_contrast_ink_mask,
)
from glyphcue.application.detector_assisted_signature import detector_assisted_signature
from glyphcue.application.visual_state_sampling import signature_distance


def _poly(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


_GLYPH_COLUMNS = list(range(60, 800, 11))
_OTHER_GLYPH_COLUMNS = list(range(60, 800, 17))

_LINE_POLY = [_poly(50, 18, 820, 46)]


def _caption_frame(
    glyph_columns=None,
    background_phase: float | None = None,
    background_level: int = 235,
    light_text: bool = False,
    occluder: tuple[int, int] | None = None,
) -> np.ndarray:
    """One caption line over a controllable background.

    `background_phase` adds a moving luminance gradient (scene motion
    behind the text); `occluder` paints a moving dark block across part
    of the line (a hand passing behind it). The glyphs themselves are
    pixel-identical in every variant.
    """
    height, width = 60, 900
    if background_phase is None:
        background = np.full((height, width), float(background_level))
    else:
        xs = np.linspace(0, 1, width)[None, :]
        background = (170 + 60 * np.sin(2 * np.pi * (xs * 2 + background_phase))).repeat(
            height, axis=0
        )
    frame = np.dstack([background] * 3).astype(np.uint8)

    if occluder is not None:
        start, end = occluder
        frame[:, start:end] = 60

    ink_value = 245 if light_text else 25
    for column in glyph_columns if glyph_columns is not None else _GLYPH_COLUMNS:
        frame[20:44, column : column + 3] = ink_value
    return frame


def _luma(frame: np.ndarray) -> np.ndarray:
    return (
        frame[..., 0] * 0.299 + frame[..., 1] * 0.587 + frame[..., 2] * 0.114
    ) * (1.0 / 255.0)


def test_a_flat_background_patch_yields_no_ink():
    patch = _luma(np.full((28, 400, 3), 200, dtype=np.uint8))

    assert not local_contrast_ink_mask(patch).any()


def test_dark_text_on_a_light_background_is_marked_as_ink():
    patch = _luma(_caption_frame()[18:46, 50:820])

    mask = local_contrast_ink_mask(patch)

    assert mask.any()
    assert mask.mean() < 0.5  # ink is the sparse class


def test_light_text_on_a_dark_background_is_marked_as_ink():
    patch = _luma(_caption_frame(light_text=True, background_level=40)[18:46, 50:820])

    mask = local_contrast_ink_mask(patch)

    assert mask.any()
    assert mask.mean() < 0.5


def test_the_ink_mask_barely_moves_when_only_the_background_luminance_changes():
    # The core Beta-P property, at mask level: identical glyphs, very
    # different background, nearly identical ink.
    bright = local_contrast_ink_mask(_luma(_caption_frame(background_level=245)[18:46, 50:820]))
    dim = local_contrast_ink_mask(_luma(_caption_frame(background_level=150)[18:46, 50:820]))

    assert float(np.mean(bright != dim)) < 0.02


def test_identical_glyphs_over_a_moving_background_stay_the_same_state():
    # The exact case that fragmented sample_b, now required to hold under
    # Beta's OWN frozen distance and 0.10 threshold.
    reference = beta_p_signature(_caption_frame(background_phase=0.0), _LINE_POLY)

    for phase in (0.1, 0.3, 0.5):
        moved = beta_p_signature(_caption_frame(background_phase=phase), _LINE_POLY)
        distance = signature_distance(reference, moved)
        assert distance < BETA_GROUP_DISTANCE_THRESHOLD, f"phase {phase} -> {distance}"


def test_identical_glyphs_under_a_moving_occluder_stay_the_same_state():
    reference = beta_p_signature(_caption_frame(occluder=(300, 420)), _LINE_POLY)
    later = beta_p_signature(_caption_frame(occluder=(500, 620)), _LINE_POLY)

    assert signature_distance(reference, later) < BETA_GROUP_DISTANCE_THRESHOLD


def _two_line_frame(glyph_columns, background_phase: float = 0.0) -> np.ndarray:
    """A two-line bilingual-style caption -- what sample_d and sample_b
    actually contain. The frozen Beta canvas reserves MAX_LINES=4 bands,
    so a ONE-line signature leaves 3/4 of the canvas permanently empty
    and divides every distance by four; the absolute 0.10 threshold is
    only meaningful against a realistic line count."""
    single = _caption_frame(glyph_columns, background_phase=background_phase)
    return np.vstack([single, single[:60]])


_TWO_LINE_POLY = [_poly(50, 18, 820, 46), _poly(50, 60, 820, 88)]


def test_different_glyphs_stay_a_different_state_even_with_the_same_background():
    a = beta_p_signature(_two_line_frame(_GLYPH_COLUMNS), _TWO_LINE_POLY)
    b = beta_p_signature(_two_line_frame(_OTHER_GLYPH_COLUMNS), _TWO_LINE_POLY)

    assert signature_distance(a, b) > BETA_GROUP_DISTANCE_THRESHOLD


def test_different_glyphs_stay_a_different_state_across_different_backgrounds_too():
    a = beta_p_signature(_two_line_frame(_GLYPH_COLUMNS, background_phase=0.0), _TWO_LINE_POLY)
    b = beta_p_signature(
        _two_line_frame(_OTHER_GLYPH_COLUMNS, background_phase=0.4), _TWO_LINE_POLY
    )

    assert signature_distance(a, b) > BETA_GROUP_DISTANCE_THRESHOLD


def test_beta_p_separates_different_glyphs_at_least_as_well_as_beta_does():
    # The non-regression contract that matters: decoupling the ink rule
    # from background luminance must not cost discriminative power. It
    # gains it -- Beta's own margin on this pair sits UNDER the threshold
    # (a pre-existing consequence of the 4-band canvas), Beta-P's clears
    # it.
    a = _two_line_frame(_GLYPH_COLUMNS)
    b = _two_line_frame(_OTHER_GLYPH_COLUMNS)

    beta_margin = signature_distance(
        detector_assisted_signature(a, _TWO_LINE_POLY),
        detector_assisted_signature(b, _TWO_LINE_POLY),
    )
    beta_p_margin = signature_distance(
        beta_p_signature(a, _TWO_LINE_POLY), beta_p_signature(b, _TWO_LINE_POLY)
    )

    assert beta_p_margin > beta_margin


def test_beta_p_improves_on_the_original_beta_for_the_same_background_change():
    # Direct before/after on the diagnosed failure: Beta's global
    # dynamic-range midpoint crosses the threshold on a pure background
    # change; Beta-P must not.
    beta_before = detector_assisted_signature(_caption_frame(background_phase=0.0), _LINE_POLY)
    beta_after = detector_assisted_signature(_caption_frame(background_phase=0.3), _LINE_POLY)
    beta_p_before = beta_p_signature(_caption_frame(background_phase=0.0), _LINE_POLY)
    beta_p_after = beta_p_signature(_caption_frame(background_phase=0.3), _LINE_POLY)

    beta_distance = signature_distance(beta_before, beta_after)
    beta_p_distance = signature_distance(beta_p_before, beta_p_after)

    assert beta_distance > BETA_GROUP_DISTANCE_THRESHOLD
    assert beta_p_distance < BETA_GROUP_DISTANCE_THRESHOLD
    assert beta_p_distance < beta_distance


def test_blank_input_produces_an_empty_signature():
    assert not beta_p_signature(_caption_frame(), []).any()


def _textured_background_frame(shift: int) -> np.ndarray:
    """Identical glyphs with a high-contrast STRUCTURED object moving
    behind them -- a stand-in for sample_a's hand/pen gesturing close to
    camera, as opposed to sample_b's smooth luminance gradients."""
    height, width = 60, 900
    frame = np.full((height, width, 3), 200, dtype=np.uint8)
    for column in range(shift, width, 37):
        frame[:, column : column + 14] = 120
    for column in _GLYPH_COLUMNS:  # the glyphs never change
        frame[20:44, column : column + 3] = 25
    return frame


def test_characterizes_beta_p_tradeoff_texture_motion_costs_what_luminance_gained():
    """CHARACTERIZATION of Beta-P's OWN weakness -- the mirror image of
    the one it fixes, and the reason this round did not pass.

    Deciding ink by contrast against a LOCAL background makes the mask
    immune to global luminance change, but it also admits any other
    locally-contrasty structure: a textured object moving behind the
    caption now perturbs the mask, where Beta's global dynamic-range
    midpoint ignored it (only near-extreme pixels survived, and the
    bright caption dominated that range).

    Measured on the real corpus: within one held caption, sample_b
    (smooth light/dark backgrounds) improved from 0.095 to 0.030 mean
    distance and 4/17 to 1/17 frames over threshold, while sample_a
    (hand/pen moving close to camera) degraded from 0.044 to 0.145 and
    0/14 to 11/14. Neither ink rule dominates; each fixture's dominant
    nuisance decides which one wins.
    """
    polygons = _LINE_POLY
    beta_reference = detector_assisted_signature(_textured_background_frame(0), polygons)
    beta_p_reference = beta_p_signature(_textured_background_frame(0), polygons)

    moved = _textured_background_frame(18)
    beta_distance = signature_distance(
        beta_reference, detector_assisted_signature(moved, polygons)
    )
    beta_p_distance = signature_distance(beta_p_reference, beta_p_signature(moved, polygons))

    # Identical text either way -- but the local rule is the one that moves.
    assert beta_p_distance > beta_distance
