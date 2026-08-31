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
