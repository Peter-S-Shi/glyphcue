"""M11 Research Gate -- Beta-S stroke-structural glyph evidence.

Two rounds of per-patch BINARIZATION have now failed in mirror-image
ways, and their failures are informative enough to close that avenue:

  * Beta (41e80f9) cuts each patch at its own dynamic-range midpoint.
    Robust to textured backgrounds (only near-extreme pixels survive,
    and a legible caption dominates that range), fragile to luminance
    change -- a pure background gradient shift moved identical text by
    0.079-0.149, past the 0.10 threshold. sample_b: 4/17 held frames
    over threshold.
  * Beta-P (fcd1df2) cuts on contrast against the LOCAL background.
    Exactly the opposite: immune to luminance change (0.0000 on the same
    gradients), fragile to texture -- any locally-contrasty structure
    moving behind the caption enters the mask. sample_a went from 0/14
    to 11/14 held frames over threshold, and 16 -> 21 representatives.

Both rules ask the same question -- "is this pixel foreground or
background?" -- and that question is answerable only from brightness,
which is exactly what the nuisances change. So Beta-S stops asking it.

Instead the evidence is STRUCTURAL: a pixel counts when it lies inside a
stroke, i.e. between two opposite-polarity intensity boundaries that are
close enough together to be a pen stroke. This is the standard
script-agnostic core of stroke-width-based text detection (SWT and
relatives), reduced to a cheap separable form -- nearest opposing
boundary scanned along the two image axes -- with no connected-component
analysis, no tracking, no recognition.

Why it decouples from both nuisances at once:

  * a boundary is a DIFFERENCE, so a flat luminance change (and, to
    first order, a smooth gradient) cancels -- what Beta-P gained;
  * a wide object has its two boundaries far apart, so it fails the
    stroke-width test no matter how high its contrast -- what Beta kept,
    and more directly than "the caption happens to own the extremes".

Text is thin by construction, at every script and every font weight; a
hand, a face, a pen, a lower-third graphic are not. That is the
invariant this round tests.

Everything else stays frozen: the detector configuration, 5 fps
sampling, the canonical band layout, the cell-mismatch distance, the
0.10 grouping threshold, the blank rule, and the
sampling -> grouping -> representative harness. Only the mask changes.
"""

from __future__ import annotations

import numpy as np

from glyphcue.application.detector_assisted_signature import detector_assisted_signature

# Declared a priori for this round and used unchanged on every fixture.
#
# The minimum step, as a fraction of the full luminance range, for an
# intensity boundary to count. This is deliberately LOW: it is not a
# foreground/background decision (that is what failed twice) and it does
# not have to separate text from anything. Discrimination comes from the
# width test below, so this only has to reject sensor noise and codec
# ringing while admitting even a faint stroke.
_BOUNDARY_CONTRAST = 0.06

# The widest run of pixels that may still be called a stroke, as a
# fraction of the detected line's own height -- so it self-scales across
# fixtures with different ROI resolutions and font sizes instead of
# being an absolute pixel count. Type is drawn with strokes well under a
# quarter of its em height at any weight; scene objects that happen to
# pass behind a caption are not.
_MAX_STROKE_TO_LINE_HEIGHT = 0.25


def _nearest_opposing(patch: np.ndarray, axis: int, forward: bool, contrast: float, reach: int):
    """Distance from each pixel to the nearest pixel that is brighter by
    at least `contrast`, scanning one direction along one axis.

    Returns `reach + 1` where no such pixel exists within reach, so an
    unbounded region reads as "no boundary" rather than as a near one.
    """
    distance = np.full(patch.shape, reach + 1, dtype=np.int32)
    for step in range(1, reach + 1):
        shifted = np.full(patch.shape, -np.inf)
        if axis == 1:
            if forward:
                shifted[:, : patch.shape[1] - step] = patch[:, step:]
            else:
                shifted[:, step:] = patch[:, : patch.shape[1] - step]
        else:
            if forward:
                shifted[: patch.shape[0] - step, :] = patch[step:, :]
            else:
                shifted[step:, :] = patch[: patch.shape[0] - step, :]
        hit = (shifted - patch) >= contrast
        distance = np.where((distance > reach) & hit, step, distance)
    return distance


def _dark_strokes_along(patch: np.ndarray, axis: int, contrast: float, reach: int) -> np.ndarray:
    """Pixels enclosed by two brighter boundaries no more than `reach`
    apart along one axis -- a dark run thin enough to be a stroke."""
    return (
        _nearest_opposing(patch, axis, False, contrast, reach)
        + _nearest_opposing(patch, axis, True, contrast, reach)
    ) <= reach + 1


def _stroke_masks(patch: np.ndarray, contrast: float, reach: int) -> tuple[np.ndarray, np.ndarray]:
    """The dark-stroke and light-stroke systems of a patch.

    Vertical strokes come from scanning rows, horizontal strokes from
    scanning columns; a glyph in any script is a union of the two, while
    a wide object is neither in whichever direction it is wide.
    """
    dark = _dark_strokes_along(patch, 1, contrast, reach) | _dark_strokes_along(
        patch, 0, contrast, reach
    )
    inverted = -patch
    light = _dark_strokes_along(inverted, 1, contrast, reach) | _dark_strokes_along(
        inverted, 0, contrast, reach
    )
    return dark, light


def stroke_structure_mask(
    patch: np.ndarray,
    boundary_contrast: float = _BOUNDARY_CONTRAST,
    max_stroke_to_height: float = _MAX_STROKE_TO_LINE_HEIGHT,
) -> np.ndarray:
    """Glyph evidence as stroke structure rather than as a
    foreground/background classification.

    The stroke-width limit scales with the line height, so the same rule
    applies unchanged to every fixture.

    Of the two stroke systems the DOMINANT one is the text: inside a
    detector box, thin stroke structure is what the box was detected for.
    Choosing once per patch -- rather than accepting both polarities
    pixelwise -- keeps the rule polarity-independent (white-on-dark and
    dark-on-light both work, with no colour prior) while refusing the
    incidental narrow gaps that any two nearby dark objects leave between
    them, which would otherwise move whenever a background object moved.
    """
    if patch.size == 0:
        return np.zeros(patch.shape, dtype=bool)

    reach = max(2, int(round(patch.shape[0] * max_stroke_to_height)))
    dark, light = _stroke_masks(patch, boundary_contrast, reach)
    return dark if dark.sum() >= light.sum() else light


def beta_s_signature(frame: np.ndarray, polygons) -> np.ndarray:
    """The Beta signature with ONLY its glyph-evidence layer swapped.

    Identical line grouping, identical crop/tighten/rescale
    canonicalization, identical canvas layout, identical blank rule and
    identical distance as `detector_assisted_signature` -- the single
    difference is what counts as glyph evidence inside a detected box.
    """
    return detector_assisted_signature(frame, polygons, ink_fn=stroke_structure_mask)
