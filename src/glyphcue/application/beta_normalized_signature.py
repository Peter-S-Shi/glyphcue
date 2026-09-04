"""M11 Research Gate -- Beta-N signature normalization corrective.

Detector-Assisted Beta (commit 41e80f9) restored 100% semantic
transition recall with zero swallowed states on all three real fixtures
-- the detector-localized, glyph-level evidence layer works. What it did
NOT fix was fragmentation: sample_b split one held caption into ~8
groups and landed at 21 representatives, one over the frozen cap.

That was diagnosed, not guessed: the detector emitted exactly 2 boxes on
50/50 sampled frames, so localization was stable. The instability came
from Beta's canonicalization, which stretched every line to a fixed
192-cell width. A ~1000px-wide caption therefore had ~5 source pixels
per cell, sampled by NEAREST NEIGHBOUR -- so a 2-3px box/ink shift
re-picked a different source pixel for essentially every cell and
flipped a large fraction of a 2-4px-wide stroke's cells at once.

Beta-N changes ONLY normalization and comparison (detector, sampling
fps, grouping threshold, blank rule, MAX_LINES and the whole
sampling -> grouping -> representative harness are untouched):

1. Aspect-preserving fixed-height normalization + padding, instead of
   stretching to a fixed width. A line is scaled by its own height and
   left-aligned into a wide canvas, so horizontal and vertical scale
   factors are equal and moderate, and line LENGTH survives as real
   evidence rather than being normalized away.
2. Area-averaged (anti-aliased) resampling producing a SOFT coverage
   map in [0, 1] rather than a hard binary mask. A sub-cell shift now
   moves cell values slightly instead of flipping them.
3. A small, explicitly bounded translation-tolerant comparison: the
   distance is the minimum over a few one- and two-cell offsets, so
   residual sub-cell misalignment cannot masquerade as a new state --
   while a genuinely displaced or different caption still scores far
   away.

The distance is normalized by total ink mass, not canvas area, so the
zero padding introduced by (1) cannot dilute the score and quietly drag
different captions under the unchanged grouping threshold.
"""

from __future__ import annotations

import numpy as np

# Declared a priori for this round and used unchanged for every fixture.
# 16x512 is a 32:1 canvas: it accommodates a typical burned-in caption
# line (a 40px-tall line up to ~1280px wide) at full canonical height
# without truncation, which is exactly the long-line case Beta crushed.
CANONICAL_HEIGHT = 16
CANONICAL_WIDTH = 512
MAX_LINES = 4

# Bounded translation tolerance, in canonical cells. Small by design:
# at 512 cells wide, 2 cells is 0.4% of the canvas.
MAX_SHIFT_X_CELLS = 2
MAX_SHIFT_Y_CELLS = 1

_INK_MIDPOINT = 0.5


def _luminance(frame: np.ndarray) -> np.ndarray:
    if frame.ndim == 3:
        return (
            frame[..., 0] * 0.299 + frame[..., 1] * 0.587 + frame[..., 2] * 0.114
        ) * (1.0 / 255.0)
    return frame.astype(np.float32) * (1.0 / 255.0)


def _binarize_ink(patch: np.ndarray) -> np.ndarray:
    """Polarity-independent ink mask, unchanged from Beta: normalize to
    the patch's own dynamic range, split at the midpoint, call the
    sparser side the ink. No color or outline prior."""
    low, high = float(patch.min()), float(patch.max())
    if high - low < 1e-6:
        return np.zeros(patch.shape, dtype=bool)
    normalized = (patch - low) / (high - low)
    dark_is_ink = normalized <= _INK_MIDPOINT
    if dark_is_ink.mean() > 0.5:
        return ~dark_is_ink
    return dark_is_ink


def _tighten_to_ink(ink: np.ndarray) -> np.ndarray:
    rows = np.flatnonzero(ink.any(axis=1))
    cols = np.flatnonzero(ink.any(axis=0))
    if rows.size == 0 or cols.size == 0:
        return ink[:0, :0]
    return ink[rows[0] : rows[-1] + 1, cols[0] : cols[-1] + 1]


def _area_average_resample(ink: np.ndarray, height: int, width: int) -> np.ndarray:
    """Anti-aliased downsample of a boolean ink mask to a float coverage
    map: each output cell is the FRACTION of its source footprint that
    was ink. This is what makes the representation move smoothly under a
    sub-cell shift, instead of nearest-neighbour's all-or-nothing flip.
    """
    source_h, source_w = ink.shape
    if source_h == 0 or source_w == 0 or height <= 0 or width <= 0:
        return np.zeros((max(height, 0), max(width, 0)), dtype=np.float64)

    values = ink.astype(np.float64)
    row_edges = (np.arange(height + 1) * source_h) / height
    col_edges = (np.arange(width + 1) * source_w) / width

    # Integrate with a cumulative sum so each output cell is an exact
    # box average over a fractional source footprint.
    row_cumulative = np.zeros((source_h + 1, source_w), dtype=np.float64)
    row_cumulative[1:] = np.cumsum(values, axis=0)
    rows_resampled = np.empty((height, source_w), dtype=np.float64)
    for index in range(height):
        start, end = row_edges[index], row_edges[index + 1]
        rows_resampled[index] = _integrate(row_cumulative, values, start, end, axis_length=source_h)

    col_cumulative = np.zeros((height, source_w + 1), dtype=np.float64)
    col_cumulative[:, 1:] = np.cumsum(rows_resampled, axis=1)
    output = np.empty((height, width), dtype=np.float64)
    for index in range(width):
        start, end = col_edges[index], col_edges[index + 1]
        output[:, index] = _integrate_columns(col_cumulative, rows_resampled, start, end, source_w)

    return np.clip(output, 0.0, 1.0)


def _integrate(cumulative: np.ndarray, values: np.ndarray, start: float, end: float, axis_length: int):
    lo, hi = int(np.floor(start)), int(np.ceil(end))
    lo = max(0, min(lo, axis_length))
    hi = max(lo + 1, min(hi, axis_length))
    total = cumulative[hi] - cumulative[lo]
    # Remove the fractional parts of the first and last source rows.
    total = total - values[lo] * (start - lo)
    total = total - values[hi - 1] * (hi - end)
    span = max(end - start, 1e-9)
    return total / span


def _integrate_columns(cumulative: np.ndarray, values: np.ndarray, start: float, end: float, axis_length: int):
    lo, hi = int(np.floor(start)), int(np.ceil(end))
    lo = max(0, min(lo, axis_length))
    hi = max(lo + 1, min(hi, axis_length))
    total = cumulative[:, hi] - cumulative[:, lo]
    total = total - values[:, lo] * (start - lo)
    total = total - values[:, hi - 1] * (hi - end)
    span = max(end - start, 1e-9)
    return total / span


def aspect_preserving_coverage_band(frame: np.ndarray, box) -> np.ndarray:
    """One detected caption line as a soft, aspect-preserving coverage
    map, left-aligned into the canonical canvas and zero-padded.

    Scaled by its own height so horizontal and vertical scale factors
    match; a line too wide to fit at full height is scaled down to fit
    the canvas width instead of being truncated.
    """
    height, width = frame.shape[0], frame.shape[1]
    x0 = max(0, min(int(box[0]), width))
    y0 = max(0, min(int(box[1]), height))
    x1 = max(x0 + 1, min(int(box[2]), width))
    y1 = max(y0 + 1, min(int(box[3]), height))

    band = np.zeros((CANONICAL_HEIGHT, CANONICAL_WIDTH), dtype=np.float64)
    patch = _luminance(frame[y0:y1, x0:x1])
    if patch.size == 0:
        return band

    ink = _tighten_to_ink(_binarize_ink(patch))
    if ink.size == 0:
        return band

    source_h, source_w = ink.shape
    scale = CANONICAL_HEIGHT / source_h
    target_w = int(round(source_w * scale))
    if target_w > CANONICAL_WIDTH:
        # Extremely wide line: fit inside rather than truncate.
        scale = CANONICAL_WIDTH / source_w
        target_w = CANONICAL_WIDTH
    target_h = max(1, min(CANONICAL_HEIGHT, int(round(source_h * scale))))
    target_w = max(1, min(CANONICAL_WIDTH, target_w))

    band[:target_h, :target_w] = _area_average_resample(ink, target_h, target_w)
    return band


def beta_normalized_signature(frame: np.ndarray, polygons) -> np.ndarray:
    """The Beta-N signature: one aspect-preserving soft coverage band per
    detected caption line, stacked top to bottom.

    Line grouping and the detector-driven blank rule are unchanged from
    Beta -- only the per-line normalization differs.
    """
    from glyphcue.application.detector_assisted_signature import (
        detected_lines_from_polygons,
    )

    canvas = np.zeros((MAX_LINES * CANONICAL_HEIGHT, CANONICAL_WIDTH), dtype=np.float64)
    for index, box in enumerate(detected_lines_from_polygons(polygons)[:MAX_LINES]):
        top = index * CANONICAL_HEIGHT
        canvas[top : top + CANONICAL_HEIGHT, :] = aspect_preserving_coverage_band(frame, box)
    return canvas


def _shifted(signature: np.ndarray, dy: int, dx: int) -> np.ndarray:
    """Translate by whole cells with zero fill (never wrap-around, which
    would let content re-enter from the opposite edge)."""
    if dy == 0 and dx == 0:
        return signature
    output = np.zeros_like(signature)
    height, width = signature.shape
    src_y0, dst_y0 = (0, dy) if dy >= 0 else (-dy, 0)
    src_x0, dst_x0 = (0, dx) if dx >= 0 else (-dx, 0)
    copy_h = height - abs(dy)
    copy_w = width - abs(dx)
    if copy_h <= 0 or copy_w <= 0:
        return output
    output[dst_y0 : dst_y0 + copy_h, dst_x0 : dst_x0 + copy_w] = signature[
        src_y0 : src_y0 + copy_h, src_x0 : src_x0 + copy_w
    ]
    return output


def signature_mass_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Total absolute coverage difference, normalized by total ink mass
    rather than canvas area -- so the zero padding that
    aspect-preserving normalization introduces cannot dilute the score
    and drag genuinely different captions under the grouping threshold.

    0.0 = identical, 1.0 = fully disjoint ink.
    """
    if a.shape != b.shape:
        return 1.0
    mass = float(a.sum() + b.sum())
    if mass <= 1e-9:
        return 0.0
    return float(np.abs(a - b).sum() / mass)


def shift_tolerant_distance(
    a: np.ndarray,
    b: np.ndarray,
    max_shift_x: int = MAX_SHIFT_X_CELLS,
    max_shift_y: int = MAX_SHIFT_Y_CELLS,
) -> float:
    """Best `signature_mass_distance` over a small, bounded set of whole-
    cell offsets. Absorbs the residual one- or two-cell misalignment left
    by ink-extent tightening; far too small to reconcile two genuinely
    different captions."""
    if a.shape != b.shape:
        return 1.0
    best = signature_mass_distance(a, b)
    for dy in range(-max_shift_y, max_shift_y + 1):
        for dx in range(-max_shift_x, max_shift_x + 1):
            if dy == 0 and dx == 0:
                continue
            best = min(best, signature_mass_distance(a, _shifted(b, dy, dx)))
    return best
