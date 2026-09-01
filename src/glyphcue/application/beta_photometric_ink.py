"""M11 Research Gate -- Beta-P photometric decoupling.

Detector-Assisted Beta (41e80f9) reached 100% semantic transition recall
with zero swallowed states on all three real fixtures, but over-split
held captions. Beta-N (5841478) tried to fix that as a GEOMETRIC problem
and made it worse; its measurements refuted the geometric premise
outright -- on 18 real frames inside one held sample_b caption the
detector box was constant at 1267x57, the tightened ink extent varied by
0.8%, and an explicit shift search recovered only 0.015 of distance.

What the same measurements did identify is PHOTOMETRIC coupling. Beta's
ink rule normalizes each patch by its own global dynamic range and cuts
at the midpoint:

    normalized = (patch - patch.min()) / (patch.max() - patch.min())
    ink = normalized <= 0.5

Both ends of that range come from whatever happens to be in the patch,
so a brighter/darker background behind pixel-identical glyphs moves the
cut and reclassifies glyph-edge pixels. Synthetically, a pure background
gradient shift scored 0.079-0.136 under Beta -- past the 0.10 grouping
threshold on identical text. sample_b is exactly that material:
alternating light/dark backgrounds with hands moving behind the captions.

Beta-P replaces ONLY that rule. Ink becomes a question of local
contrast: how far a pixel departs from the background immediately around
it, rather than where it sits in the patch's global luminance span. This
is the standard answer to uneven illumination in document/scene-text
binarization (Niblack/Sauvola-style local thresholding), reduced here to
its simplest form -- a local mean plus a fixed minimum contrast -- so it
introduces no new tunable per fixture.

Everything else in the Beta pipeline stays frozen: the detector config,
5 fps sampling, the canonical band layout, the cell-mismatch distance,
the 0.10 grouping threshold, the blank rule, and the
sampling -> grouping -> representative harness.
"""

from __future__ import annotations

import numpy as np

from glyphcue.application.detector_assisted_signature import detector_assisted_signature

# Declared a priori for this round and used unchanged on every fixture.
#
# The local background window is tied to the LINE'S OWN HEIGHT rather
# than an absolute pixel count, so it self-scales across fixtures with
# different ROI resolutions and font sizes. A window one line-height
# across covers roughly one glyph's worth of area; typical text ink
# coverage is well under half of that, so the window mean is dominated
# by background even directly on top of a stroke.
_WINDOW_TO_LINE_HEIGHT = 1.0

# Minimum separation from the local background, as a fraction of the full
# luminance range, for a pixel to count as glyph ink. Burned-in subtitles
# are authored to be legible -- typically near-maximal contrast, usually
# with an outline -- so 10% is a conservative floor that any legible
# caption clears while ordinary background texture does not. It also
# keeps flat, text-free regions empty instead of amplifying noise the way
# a purely relative (divide-by-local-std) rule would.
_MIN_LOCAL_CONTRAST = 0.10


def _box_mean(image: np.ndarray, window: int) -> np.ndarray:
    """Mean over a square window centred on each pixel, via an integral
    image. Edges use the truncated window's real area rather than padding
    with invented values, which would bias the background estimate
    exactly where captions often sit."""
    height, width = image.shape
    integral = np.zeros((height + 1, width + 1), dtype=np.float64)
    integral[1:, 1:] = image.cumsum(axis=0).cumsum(axis=1)

    radius = window // 2
    rows = np.arange(height)
    cols = np.arange(width)
    y0 = np.clip(rows - radius, 0, height)
    y1 = np.clip(rows + radius + 1, 0, height)
    x0 = np.clip(cols - radius, 0, width)
    x1 = np.clip(cols + radius + 1, 0, width)

    totals = (
        integral[np.ix_(y1, x1)]
        - integral[np.ix_(y0, x1)]
        - integral[np.ix_(y1, x0)]
        + integral[np.ix_(y0, x0)]
    )
    areas = (y1 - y0)[:, None] * (x1 - x0)[None, :]
    return totals / np.maximum(areas, 1)


def local_contrast_ink_mask(
    patch: np.ndarray,
    window_to_height: float = _WINDOW_TO_LINE_HEIGHT,
    min_contrast: float = _MIN_LOCAL_CONTRAST,
) -> np.ndarray:
    """Glyph ink decided by contrast against the LOCAL background.

    A pixel is a candidate if it departs from its own neighbourhood mean
    by at least `min_contrast`; of the two candidate polarities (darker
    than local background, brighter than it) the SPARSER one is the ink
    -- preserving Beta's polarity-independence, so white-on-dark,
    dark-on-light and coloured captions all work with no colour prior.

    Because the reference is a local mean rather than the patch's global
    min/max, a background that brightens, darkens, or moves behind the
    text does not move the decision boundary for the glyph pixels.
    """
    if patch.size == 0:
        return np.zeros(patch.shape, dtype=bool)

    window = max(3, int(round(patch.shape[0] * window_to_height)))
    if window % 2 == 0:
        window += 1

    background = _box_mean(patch, window)
    residual = patch - background

    darker = residual <= -min_contrast
    brighter = residual >= min_contrast

    darker_count = int(darker.sum())
    brighter_count = int(brighter.sum())
    if darker_count == 0 and brighter_count == 0:
        return np.zeros(patch.shape, dtype=bool)
    if brighter_count == 0:
        return darker
    if darker_count == 0:
        return brighter
    return darker if darker_count <= brighter_count else brighter


def beta_p_signature(frame: np.ndarray, polygons) -> np.ndarray:
    """The Beta signature with ONLY its photometric layer swapped.

    Identical line grouping, identical crop/tighten/rescale
    canonicalization, identical canvas layout and identical blank rule as
    `detector_assisted_signature` -- the single difference is which
    pixels count as glyph ink.
    """
    return detector_assisted_signature(frame, polygons, ink_fn=local_contrast_ink_mask)
