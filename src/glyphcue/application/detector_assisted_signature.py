"""M11 Research Gate -- Detector-Assisted Beta signature.

The Alpha family (whole-ROI edge mask, then edge + temporal persistence
+ connected-component size, causal then centered) was stopped by the
Generalization Gate (commit faf8bc4): on `sample_b` two textually
different captions with similar visual shape/position/density merged
into one group, so a real subtitle state produced no representative at
all. A purely structural, ROI-wide signature has no way to know that
the *text* changed.

This module keeps the detector's job to LOCALIZATION only -- it never
recognizes text -- and then answers "did the subtitle state change?"
from the glyph pixels INSIDE the detected regions:

    ROI frame + detected polygons
      -> group boxes into caption lines (vertical-overlap merge)
      -> per line: crop, tighten to the ink's own extent, rescale to one
         canonical band, binarize polarity-independently
      -> stack bands into a fixed canvas = the signature

Box geometry alone (count / position / width / height) is deliberately
NOT the state identity: `sample_b` already proved different captions can
share almost identical geometry. Geometry only decides WHERE to look and
how to normalize scale; the identity is the glyph ink itself.

Rescaling every line to one canonical band is what makes the comparison
meaningful across detector box jitter and across fixtures with different
ROI resolutions -- an ink map, not a resolution-dependent edge count.
"""

from __future__ import annotations

from typing import Callable

import numpy as np

# Declared a priori for the whole Beta round and used unchanged for every
# fixture -- no per-fixture variants.
CANONICAL_BAND_HEIGHT = 24
CANONICAL_BAND_WIDTH = 192
MAX_LINES = 4

_LINE_VERTICAL_OVERLAP_RATIO = 0.3

# A box's own ink is the sparser class after normalization; cells at or
# below this fraction of the band's own dynamic range count as ink.
_INK_MIDPOINT = 0.5

LineBox = tuple[int, int, int, int]  # x0, y0, x1, y1


def _polygon_bounds(polygon) -> LineBox:
    points = np.asarray(polygon, dtype=np.float64).reshape(-1, 2)
    x0, y0 = points.min(axis=0)
    x1, y1 = points.max(axis=0)
    return int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1))


def _vertically_overlapping(a: LineBox, b: LineBox) -> bool:
    overlap = min(a[3], b[3]) - max(a[1], b[1])
    if overlap <= 0:
        return False
    shortest = min(a[3] - a[1], b[3] - b[1])
    if shortest <= 0:
        return False
    return (overlap / shortest) >= _LINE_VERTICAL_OVERLAP_RATIO


def detected_lines_from_polygons(polygons) -> list[LineBox]:
    """Groups detector polygons into caption LINES, top to bottom.

    A detector routinely splits one visual caption line into several
    boxes; those must collapse into one line, or the signature's band
    layout would shift purely because the detector fragmented a line
    differently on two frames showing identical text.
    """
    boxes = sorted((_polygon_bounds(p) for p in polygons), key=lambda b: (b[1], b[0]))

    lines: list[LineBox] = []
    for box in boxes:
        if lines and _vertically_overlapping(lines[-1], box):
            previous = lines[-1]
            lines[-1] = (
                min(previous[0], box[0]),
                min(previous[1], box[1]),
                max(previous[2], box[2]),
                max(previous[3], box[3]),
            )
        else:
            lines.append(box)
    return lines


def _luminance(frame: np.ndarray) -> np.ndarray:
    if frame.ndim == 3:
        return (
            frame[..., 0] * 0.299 + frame[..., 1] * 0.587 + frame[..., 2] * 0.114
        ) * (1.0 / 255.0)
    return frame.astype(np.float32) * (1.0 / 255.0)


def _binarize_ink(patch: np.ndarray) -> np.ndarray:
    """Polarity-independent ink mask: normalize the patch to its own
    dynamic range, split at the midpoint, and call the SPARSER side the
    ink. Text occupies fewer pixels than its own background, so this
    holds for white-on-dark, dark-on-light, yellow-on-light and so on --
    no color or outline prior anywhere."""
    low, high = float(patch.min()), float(patch.max())
    if high - low < 1e-6:
        return np.zeros(patch.shape, dtype=bool)
    normalized = (patch - low) / (high - low)
    dark_is_ink = normalized <= _INK_MIDPOINT
    if dark_is_ink.mean() > 0.5:
        return ~dark_is_ink
    return dark_is_ink


def _tighten_to_ink(patch: np.ndarray, ink: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    rows = np.flatnonzero(ink.any(axis=1))
    cols = np.flatnonzero(ink.any(axis=0))
    if rows.size == 0 or cols.size == 0:
        return patch, ink
    return (
        patch[rows[0] : rows[-1] + 1, cols[0] : cols[-1] + 1],
        ink[rows[0] : rows[-1] + 1, cols[0] : cols[-1] + 1],
    )


def _resize_nearest(mask: np.ndarray, height: int, width: int) -> np.ndarray:
    source_h, source_w = mask.shape
    if source_h == 0 or source_w == 0:
        return np.zeros((height, width), dtype=bool)
    rows = np.minimum((np.arange(height) * source_h) // height, source_h - 1)
    cols = np.minimum((np.arange(width) * source_w) // width, source_w - 1)
    return mask[np.ix_(rows, cols)]


def canonical_line_band(
    frame: np.ndarray,
    box: LineBox,
    ink_fn: Callable[[np.ndarray], np.ndarray] = _binarize_ink,
) -> np.ndarray:
    """One detected caption line reduced to a fixed-size ink map.

    Crop -> binarize -> tighten to the ink's OWN extent -> rescale to the
    canonical band. Tightening before rescaling is what makes the band
    stable when the detector's box wobbles by a few pixels on identical
    content, and what makes two fixtures at different ROI resolutions
    directly comparable.

    `ink_fn` decides which pixels are glyph ink. It defaults to Beta's
    original per-patch dynamic-range midpoint; Beta-P injects a
    local-contrast rule instead, leaving every other step of this
    canonicalization identical.
    """
    height, width = frame.shape[0], frame.shape[1]
    x0 = max(0, min(int(box[0]), width))
    y0 = max(0, min(int(box[1]), height))
    x1 = max(x0 + 1, min(int(box[2]), width))
    y1 = max(y0 + 1, min(int(box[3]), height))

    patch = _luminance(frame[y0:y1, x0:x1])
    if patch.size == 0:
        return np.zeros((CANONICAL_BAND_HEIGHT, CANONICAL_BAND_WIDTH), dtype=bool)

    ink = ink_fn(patch)
    _tight_patch, tight_ink = _tighten_to_ink(patch, ink)
    return _resize_nearest(tight_ink, CANONICAL_BAND_HEIGHT, CANONICAL_BAND_WIDTH)


def detector_assisted_signature(
    frame: np.ndarray,
    polygons,
    ink_fn: Callable[[np.ndarray], np.ndarray] = _binarize_ink,
) -> np.ndarray:
    """The Beta signature for one ROI-cropped frame: the glyph ink inside
    each detected caption line, each rescaled to one canonical band and
    stacked top to bottom into a fixed canvas.

    No detected text at all is an EXPLICIT blank state -- an all-False
    canvas -- decided by the detector rather than by a pixel-density
    threshold, which is the rule that failed to transfer across fixtures
    in the Alpha family.
    """
    canvas = np.zeros(
        (MAX_LINES * CANONICAL_BAND_HEIGHT, CANONICAL_BAND_WIDTH), dtype=bool
    )
    lines = detected_lines_from_polygons(polygons)[:MAX_LINES]
    for index, box in enumerate(lines):
        band = canonical_line_band(frame, box, ink_fn=ink_fn)
        top = index * CANONICAL_BAND_HEIGHT
        canvas[top : top + CANONICAL_BAND_HEIGHT, :] = band
    return canvas
