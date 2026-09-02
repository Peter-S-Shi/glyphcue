import numpy as np
import pytest

from glyphcue.application.beta_detector_dry_run import BETA_GROUP_DISTANCE_THRESHOLD
from glyphcue.application.beta_photometric_ink import beta_p_signature
from glyphcue.application.beta_stroke_structural import (
    beta_s_signature,
    stroke_structure_mask,
)
from glyphcue.application.detector_assisted_signature import detector_assisted_signature
from glyphcue.application.visual_state_sampling import signature_distance


def _poly(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


_GLYPH_COLUMNS = list(range(60, 800, 11))
_OTHER_GLYPH_COLUMNS = list(range(60, 800, 17))

_LINE_POLY = [_poly(50, 18, 820, 46)]
_TWO_LINE_POLY = [_poly(50, 18, 820, 46), _poly(50, 60, 820, 88)]


def _caption_frame(
    glyph_columns=None,
    background_level: int = 235,
    background_phase: float | None = None,
    texture_shift: int | None = None,
    light_text: bool = False,
) -> np.ndarray:
    """One caption line over a controllable background.

    Three independent nuisances, matching what the real corpus contains
    and what the previous two rounds each failed on:
      * `background_level`  -- a flat luminance change (sample_b's cuts)
      * `background_phase`  -- a moving smooth gradient (sample_b's pans)
      * `texture_shift`     -- a moving high-contrast STRUCTURED object
                               (sample_a's hand/pen close to camera)
    The glyphs themselves are pixel-identical in every variant.
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

    if texture_shift is not None:
        for column in range(texture_shift, width, 37):
            frame[:, column : column + 14] = 120

    ink_value = 245 if light_text else 25
    for column in glyph_columns if glyph_columns is not None else _GLYPH_COLUMNS:
        frame[20:44, column : column + 3] = ink_value
    return frame


def _two_line_frame(glyph_columns=None, **kwargs) -> np.ndarray:
    """A two-line caption -- what sample_d and sample_b actually contain.
    The frozen canvas reserves MAX_LINES=4 bands, so a one-line signature
    leaves 3/4 of the canvas empty and divides every distance by four;
    the absolute 0.10 threshold is only meaningful at a realistic line
    count."""
    single = _caption_frame(glyph_columns, **kwargs)
    return np.vstack([single, single[:60]])


def _luma(frame: np.ndarray) -> np.ndarray:
    return (
        frame[..., 0] * 0.299 + frame[..., 1] * 0.587 + frame[..., 2] * 0.114
    ) * (1.0 / 255.0)


def _line_patch(frame: np.ndarray) -> np.ndarray:
    return _luma(frame[18:46, 50:820])


# --- mask level: what counts as stroke structure -------------------------


def test_a_flat_patch_has_no_stroke_structure():
    assert not stroke_structure_mask(_luma(np.full((28, 400, 3), 200, dtype=np.uint8))).any()


def test_a_smooth_luminance_ramp_has_no_stroke_structure():
    # A gradient has edges everywhere and strokes nowhere; a pure
    # gradient-magnitude rule would light up, a paired-boundary rule
    # must not.
    ramp = np.linspace(0.1, 0.9, 400)[None, :].repeat(28, axis=0)

    assert not stroke_structure_mask(ramp).any()


def test_dark_thin_strokes_on_a_light_background_are_stroke_structure():
    mask = stroke_structure_mask(_line_patch(_caption_frame()))

    assert mask.any()
    assert mask.mean() < 0.5  # strokes are the sparse class


def test_light_thin_strokes_on_a_dark_background_are_stroke_structure():
    mask = stroke_structure_mask(
        _line_patch(_caption_frame(light_text=True, background_level=40))
    )

    assert mask.any()
    assert mask.mean() < 0.5


def test_a_wide_high_contrast_background_band_is_not_stroke_structure():
    # The sample_a failure mode at mask level: an object moving behind
    # the caption is high-contrast but WIDE, so it must not become
    # evidence. This is the property neither previous ink rule had --
    # both classified purely on brightness, which a wide dark object
    # satisfies exactly as well as a glyph does.
    height, width = 28, 400
    patch = np.full((height, width), 0.8)
    patch[:, 100:160] = 0.2

    assert not stroke_structure_mask(patch).any()


def test_stroke_structure_survives_when_a_wide_band_passes_behind_it():
    over_background = stroke_structure_mask(_line_patch(_caption_frame()))
    over_texture = stroke_structure_mask(_line_patch(_caption_frame(texture_shift=0)))

    assert over_texture.any()
    assert float(np.mean(over_background != over_texture)) < 0.05


# --- signature level: the three frozen same/different-state contracts ----


def test_identical_glyphs_under_a_flat_luminance_change_stay_the_same_state():
    bright = beta_s_signature(_two_line_frame(background_level=245), _TWO_LINE_POLY)
    dim = beta_s_signature(_two_line_frame(background_level=150), _TWO_LINE_POLY)

    assert signature_distance(bright, dim) < BETA_GROUP_DISTANCE_THRESHOLD


def test_identical_glyphs_over_a_moving_smooth_gradient_stay_the_same_state():
    reference = beta_s_signature(_two_line_frame(background_phase=0.0), _TWO_LINE_POLY)

    for phase in (0.1, 0.3, 0.5):
        moved = beta_s_signature(_two_line_frame(background_phase=phase), _TWO_LINE_POLY)
        distance = signature_distance(reference, moved)
        assert distance < BETA_GROUP_DISTANCE_THRESHOLD, f"phase {phase} -> {distance}"


def test_identical_glyphs_over_a_moving_textured_object_stay_the_same_state():
    # The case that broke Beta-P (0.0605-0.0947 drift synthetically,
    # 11/14 frames over threshold on sample_a).
    reference = beta_s_signature(_two_line_frame(texture_shift=0), _TWO_LINE_POLY)

    for shift in (9, 18, 27):
        moved = beta_s_signature(_two_line_frame(texture_shift=shift), _TWO_LINE_POLY)
        distance = signature_distance(reference, moved)
        assert distance < BETA_GROUP_DISTANCE_THRESHOLD, f"shift {shift} -> {distance}"


def test_different_glyphs_stay_a_different_state_on_the_same_background():
    a = beta_s_signature(_two_line_frame(_GLYPH_COLUMNS), _TWO_LINE_POLY)
    b = beta_s_signature(_two_line_frame(_OTHER_GLYPH_COLUMNS), _TWO_LINE_POLY)

    assert signature_distance(a, b) > BETA_GROUP_DISTANCE_THRESHOLD


def test_characterizes_the_distance_scale_depending_on_how_many_lines_are_detected():
    """CHARACTERIZATION of the M11 Beta-S Signature Discriminability
    Gate's root-cause finding. Not a bug this round fixes.

    The signature is a FIXED canvas of MAX_LINES canonical bands and the
    distance is the mismatch fraction over all of it, so an unoccupied
    band contributes zeros to both operands and dilutes the result. The
    measured distance between two captions therefore scales with how
    many bands the detector happened to FILL -- not with how different
    the captions are.

    That is what a hand-drawn ROI changes. Cropping tighter can exclude
    the second line of a two-line caption, and every distance in that
    run then halves. Measured on the real corpus (24 cached replays,
    same detector, same signature, only the ROI perturbed):

        sample_d  frozen ROI       2.00 lines   mean pairwise 0.1930
        sample_d  hand-drawn tight 1.00 line    mean pairwise 0.0895
        sample_b  frozen ROI       2.00 lines   mean pairwise 0.2027
        sample_b  hand-drawn tight 0.92 lines   mean pairwise 0.1034

    Exactly the factor of two, and it is what pushes the separation
    between two genuinely different captions (~0.20 -> ~0.095) below the
    frozen 0.10 grouping threshold, which is what the earlier rounds
    observed downstream as a swallowed state. The signature did not get
    worse at telling captions apart; the ruler shrank.

    This also fixes the meaning of 0.10: it is not a property of caption
    content, it is entangled with a mean band occupancy of about two.
    The obvious corrective -- normalize the mismatch over the OCCUPIED
    bands instead of the whole canvas -- does remove the ROI dependence
    (the real per-band figures converge to ~0.45 across every variant),
    but it multiplies every distance by MAX_LINES/occupied, so the
    frozen threshold no longer means anything and both the scale and the
    operating point would have to be re-derived together. That is out of
    scope for this gate, which may not move 0.10, so no corrective is
    applied here.
    """
    one_line = [_LINE_POLY[0]]
    a_one = beta_s_signature(_two_line_frame(_GLYPH_COLUMNS), one_line)
    b_one = beta_s_signature(_two_line_frame(_OTHER_GLYPH_COLUMNS), one_line)
    a_two = beta_s_signature(_two_line_frame(_GLYPH_COLUMNS), _TWO_LINE_POLY)
    b_two = beta_s_signature(_two_line_frame(_OTHER_GLYPH_COLUMNS), _TWO_LINE_POLY)

    one_band = signature_distance(a_one, b_one)
    two_bands = signature_distance(a_two, b_two)

    # The captions differ by exactly as much either way -- the second
    # line carries the same change the first one does.
    assert one_band > 0
    assert two_bands == pytest.approx(2 * one_band, rel=0.05)

    # The consequence, stated against the real threshold: the SAME pair
    # of genuinely different captions lands on opposite sides of it
    # purely because of how the ROI was drawn.
    assert two_bands > BETA_GROUP_DISTANCE_THRESHOLD
    assert one_band < BETA_GROUP_DISTANCE_THRESHOLD


def test_different_glyphs_stay_a_different_state_across_backgrounds_too():
    a = beta_s_signature(_two_line_frame(_GLYPH_COLUMNS, background_phase=0.0), _TWO_LINE_POLY)
    b = beta_s_signature(
        _two_line_frame(_OTHER_GLYPH_COLUMNS, background_phase=0.4), _TWO_LINE_POLY
    )

    assert signature_distance(a, b) > BETA_GROUP_DISTANCE_THRESHOLD


def test_blank_input_produces_an_empty_signature():
    assert not beta_s_signature(_caption_frame(), []).any()


# --- head-to-head against both previous ink rules ------------------------


def test_beta_s_is_stabler_than_both_predecessors_on_a_moving_gradient():
    # Beta's weakness (fixed by Beta-P): flat/gradient luminance change.
    before = _two_line_frame(background_phase=0.0)
    after = _two_line_frame(background_phase=0.3)

    beta = signature_distance(
        detector_assisted_signature(before, _TWO_LINE_POLY),
        detector_assisted_signature(after, _TWO_LINE_POLY),
    )
    beta_s = signature_distance(
        beta_s_signature(before, _TWO_LINE_POLY), beta_s_signature(after, _TWO_LINE_POLY)
    )

    assert beta_s < beta


def test_beta_s_is_stabler_than_both_predecessors_on_moving_texture():
    # Beta-P's weakness (the reason THAT round failed): a structured
    # object moving behind the caption.
    before = _two_line_frame(texture_shift=0)
    after = _two_line_frame(texture_shift=18)

    beta_p = signature_distance(
        beta_p_signature(before, _TWO_LINE_POLY), beta_p_signature(after, _TWO_LINE_POLY)
    )
    beta_s = signature_distance(
        beta_s_signature(before, _TWO_LINE_POLY), beta_s_signature(after, _TWO_LINE_POLY)
    )

    assert beta_s < beta_p
