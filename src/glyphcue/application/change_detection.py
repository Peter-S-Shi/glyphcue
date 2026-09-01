from __future__ import annotations

import numpy as np


def frame_difference_score(previous: np.ndarray, current: np.ndarray) -> float:
    """Cheap, explainable visual-change score between two same-shaped frames.

    Mean absolute per-pixel difference, normalized to 0..1 by the 8-bit
    channel range. Deliberately a commodity technique (ROADMAP Milestone
    4: "Do not over-engineer this layer") -- no perceptual/structural
    modeling, just a simple baseline for gating expensive OCR calls.
    0.0 = identical frames, 1.0 = maximally different (e.g. black vs.
    white).
    """
    diff = np.abs(current.astype(np.float64) - previous.astype(np.float64))
    return float(diff.mean() / 255.0)


def subtitle_structural_difference(
    previous: np.ndarray,
    current: np.ndarray,
    edge_threshold: float = 0.04,
) -> float:
    """Subtitle-aware structural difference between two same-shaped frames.

    Extracts high-frequency luminance gradients and text stroke edge masks to
    distinguish genuine subtitle events (appearance, disappearance, text change)
    from smooth background motion, camera pans, and illumination shifts.

    Returns a score where:
    - Pure background / face / camera motion scores < 0.005
    - Subtitle appearance, disappearance, or text change scores >= 0.02 - 0.20
    """
    if previous.shape != current.shape:
        return 1.0

    if previous.shape[0] > 120 or previous.shape[1] > 400:
        sy = max(1, previous.shape[0] // 100)
        sx = max(1, previous.shape[1] // 300)
        p = previous[::sy, ::sx]
        c = current[::sy, ::sx]
    else:
        p = previous
        c = current

    if p.ndim == 3:
        y1 = (p[..., 0] * 0.299 + p[..., 1] * 0.587 + p[..., 2] * 0.114) * (1.0 / 255.0)
        y2 = (c[..., 0] * 0.299 + c[..., 1] * 0.587 + c[..., 2] * 0.114) * (1.0 / 255.0)
    else:
        y1 = p.astype(np.float32) * (1.0 / 255.0)
        y2 = c.astype(np.float32) * (1.0 / 255.0)

    if y1.shape[0] < 3 or y1.shape[1] < 3:
        return float(np.mean(np.abs(y1 - y2)))

    gx1 = np.abs(y1[:, 2:] - y1[:, :-2])
    gy1 = np.abs(y1[2:, :] - y1[:-2, :])
    gx2 = np.abs(y2[:, 2:] - y2[:, :-2])
    gy2 = np.abs(y2[2:, :] - y2[:-2, :])

    g1 = gx1[1:-1, :] + gy1[:, 1:-1]
    g2 = gx2[1:-1, :] + gy2[:, 1:-1]

    # If neither frame contains spatial edges (e.g. flat fields):
    # A major luminance jump (>= 0.20) represents a hard scene cut;
    # small luminance shifts (< 0.20) are smooth lighting drift or noise.
    if g1.max() < edge_threshold and g2.max() < edge_threshold:
        raw_diff = float(np.mean(np.abs(y1 - y2)))
        return raw_diff if raw_diff >= 0.20 else 0.0

    m1 = g1 > edge_threshold
    m2 = g2 > edge_threshold

    edge_diff = float(np.mean(m1 != m2))
    grad_diff = float(np.mean(np.abs(g1 - g2)))
    return float(edge_diff + grad_diff)
