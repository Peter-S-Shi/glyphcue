from __future__ import annotations

import numpy as np

from glyphcue.domain.roi import ROI


def crop_to_roi(frame: np.ndarray, roi: ROI) -> np.ndarray:
    """Crop `frame` (H×W×C array) to `roi`'s fractional region.

    ROI coordinates are fractional (0..1) frame coordinates, resolution
    independent; this converts them to this specific frame's pixel grid.
    """
    height, width = frame.shape[0], frame.shape[1]
    x0 = int(round(roi.x * width))
    y0 = int(round(roi.y * height))
    x1 = int(round((roi.x + roi.width) * width))
    y1 = int(round((roi.y + roi.height) * height))
    return frame[y0:y1, x0:x1]
