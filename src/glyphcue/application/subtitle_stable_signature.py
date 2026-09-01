"""M11 Research Gate -- Alpha-D corrective experiment.

The Alpha (whole-ROI edge-mask) signature proved dominated by ordinary
human motion inside a talking-head ROI (hair/face/shoulder edges), not
subtitle text: commit 973157b found ~49% mean edge density on stable
frames and 48 representatives at 5 fps on the frozen private fixture.

This module is a cheap, subtitle-SPECIFIC visual signature combining
three mature, script/color-agnostic cues instead of raw edge density:

1. Edge presence -- the same luminance-gradient extraction already used
   by `visual_state_sampling.subtitle_visual_signature` and production's
   `change_detection.subtitle_structural_difference`.
2. Temporal persistence -- an edge only counts if it holds at the SAME
   pixel across a short trailing window of natively-decoded frames (not
   just sampled ones). Burned-in subtitle strokes are pixel-locked for
   their whole on-screen duration; ordinary human motion (talking, hair
   sway, shoulder movement) is not -- its edges shift position frame to
   frame even within a fraction of a second, so they wash out of a
   temporal-persistence ratio while held text does not. This is the
   scene-text literature's basic "stable keyframe" intuition, adapted
   here as a per-pixel ratio rather than a whole-frame classifier.
3. Connected-component size filtering -- after (1) AND (2), reject any
   connected blob larger than a small fraction of the signature grid.
   Subtitle text renders as many small, separated stroke components; a
   face/hair/shoulder edge cluster that happens to also be locally
   persistent (a static eyebrow, a glasses rim, a shirt collar seam)
   still tends to form one much larger connected region than a single
   character stroke once the whole ROI band is considered.

Deliberately NOT used: text color, a fixed white-text/black-outline
assumption, or a fixed subtitle position narrower than the ROI itself --
all three would be fragile, sample_d-specific shortcuts. No OCR, no
text/object detector, no tracking: connected-component labeling below is
a ~30-line pure numpy/Python union-find, not a vendored CV library.
"""

from __future__ import annotations

from collections import deque

import numpy as np

_DEFAULT_EDGE_THRESHOLD = 0.04
_DEFAULT_MAX_SIGNATURE_HEIGHT = 80
_DEFAULT_MAX_SIGNATURE_WIDTH = 240
_DEFAULT_STABILITY_WINDOW_SECONDS = 0.4
_DEFAULT_PERSISTENCE_THRESHOLD = 0.6
_DEFAULT_MAX_COMPONENT_FRACTION = 0.12


def _luminance(frame: np.ndarray) -> np.ndarray:
    if frame.ndim == 3:
        return (
            frame[..., 0] * 0.299 + frame[..., 1] * 0.587 + frame[..., 2] * 0.114
        ) * (1.0 / 255.0)
    return frame.astype(np.float32) * (1.0 / 255.0)


def downsampled_edge_mask(
    roi_frame: np.ndarray,
    edge_threshold: float = _DEFAULT_EDGE_THRESHOLD,
    max_height: int = _DEFAULT_MAX_SIGNATURE_HEIGHT,
    max_width: int = _DEFAULT_MAX_SIGNATURE_WIDTH,
) -> np.ndarray:
    """Raw (pre-stability, pre-component-filter) edge mask at a bounded
    resolution -- the same downsample-then-gradient technique as
    `visual_state_sampling.subtitle_visual_signature`, exposed here so
    the stability buffer and the final sample share one consistent grid."""
    if roi_frame.shape[0] > max_height or roi_frame.shape[1] > max_width:
        sy = max(1, roi_frame.shape[0] // max_height)
        sx = max(1, roi_frame.shape[1] // max_width)
        frame = roi_frame[::sy, ::sx]
    else:
        frame = roi_frame

    y = _luminance(frame)
    if y.shape[0] < 3 or y.shape[1] < 3:
        return np.zeros_like(y, dtype=bool)
    gx = np.abs(y[:, 2:] - y[:, :-2])
    gy = np.abs(y[2:, :] - y[:-2, :])
    g = gx[1:-1, :] + gy[:, 1:-1]
    return g > edge_threshold


class EdgeStabilityBuffer:
    """Trailing, time-windowed (not frame-count-windowed, so it behaves
    the same regardless of the source video's native frame rate) buffer
    of recent edge masks, used to compute a per-pixel temporal
    persistence ratio -- what fraction of the last `window_seconds` of
    natively-decoded frames had an edge at this exact pixel."""

    def __init__(self, window_seconds: float = _DEFAULT_STABILITY_WINDOW_SECONDS) -> None:
        self._window_seconds = window_seconds
        self._entries: deque[tuple[float, np.ndarray]] = deque()

    def push(self, timestamp: float, edge_mask: np.ndarray) -> None:
        self._entries.append((timestamp, edge_mask))
        cutoff = timestamp - self._window_seconds
        while self._entries and self._entries[0][0] < cutoff:
            self._entries.popleft()

    def persistence_ratio(self) -> np.ndarray | None:
        """None when nothing has been pushed yet; otherwise a same-shape
        float grid in [0, 1]."""
        if not self._entries:
            return None
        stack = np.stack([mask for _, mask in self._entries], axis=0)
        return stack.mean(axis=0)


def _connected_component_sizes(mask: np.ndarray) -> np.ndarray:
    """4-connectivity connected-component labeling via a plain
    union-find, deliberately dependency-free (no scipy/cv2) -- returns,
    for every True cell, the pixel count of the component it belongs to
    (0 for False cells). Cost is proportional to the number of True
    cells actually visited via a two-pass row scan, not the full grid,
    so it stays cheap once persistence filtering has already sparsified
    the mask."""
    height, width = mask.shape
    labels = np.zeros((height, width), dtype=np.int32)
    parent = [0]

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    next_label = 1
    for i in range(height):
        row = mask[i]
        if not row.any():
            continue
        label_row_above = labels[i - 1] if i > 0 else None
        for j in range(width):
            if not row[j]:
                continue
            left = labels[i, j - 1] if j > 0 and row[j - 1] else 0
            up = label_row_above[j] if label_row_above is not None and mask[i - 1, j] else 0
            if left and up:
                union(left, up)
                labels[i, j] = find(left)
            elif left:
                labels[i, j] = find(left)
            elif up:
                labels[i, j] = find(up)
            else:
                parent.append(next_label)
                labels[i, j] = next_label
                next_label += 1

    if next_label == 1:
        return np.zeros((height, width), dtype=np.int64)

    roots = np.array([find(i) for i in range(next_label)], dtype=np.int32)
    resolved = roots[labels]
    counts = np.bincount(resolved.ravel(), minlength=next_label)
    counts[0] = 0
    return counts[resolved]


def filter_large_components(
    mask: np.ndarray, max_component_fraction: float = _DEFAULT_MAX_COMPONENT_FRACTION
) -> np.ndarray:
    """Drops any connected component larger than `max_component_fraction`
    of the grid's total cell count -- text renders as many small,
    disjoint stroke components; a large blob is background/body
    structure, not a glyph."""
    if not mask.any():
        return mask
    total_cells = mask.size
    sizes = _connected_component_sizes(mask)
    return mask & (sizes <= max_component_fraction * total_cells)


def subtitle_stable_signature(
    edge_mask: np.ndarray,
    stability_buffer: EdgeStabilityBuffer,
    persistence_threshold: float = _DEFAULT_PERSISTENCE_THRESHOLD,
    max_component_fraction: float = _DEFAULT_MAX_COMPONENT_FRACTION,
) -> np.ndarray:
    """Combines the three cues into one boolean signature: edge AND
    temporally-persistent AND not part of an oversized connected blob."""
    persistence = stability_buffer.persistence_ratio()
    if persistence is None:
        stable = edge_mask
    else:
        stable = edge_mask & (persistence >= persistence_threshold)
    return filter_large_components(stable, max_component_fraction)
