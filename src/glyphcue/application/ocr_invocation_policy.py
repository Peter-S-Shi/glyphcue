from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np

from glyphcue.application.change_detection import frame_difference_score


@runtime_checkable
class OcrInvocationPolicy(Protocol):
    """Decides, per analyzed (ROI-cropped) frame, whether it is worth
    an OCR call. This is the seam ROADMAP Milestone 4's "OCR invocation
    policy" scope names: OCR should run when evidence suggests subtitle
    state may have changed or needs confirmation, never on every frame
    by default.
    """

    def should_ocr(self, roi_frame: np.ndarray, timestamp: float) -> bool: ...


class ChangeTriggeredOcrPolicy:
    """The default, selective policy: OCR the first frame (to establish
    a baseline), OCR again whenever `frame_difference_score` against the
    last-OCR'd frame exceeds `change_threshold`, and otherwise force a
    periodic confirmation OCR every `max_gap_seconds` even without a
    detected change (state could have drifted without a large enough
    single-frame difference, e.g. a slow fade).

    Deliberately a commodity technique -- no novelty claim is made about
    this change-detection approach (ROADMAP Milestone 4, gate 8).
    """

    def __init__(self, change_threshold: float = 0.02, max_gap_seconds: float = 2.0) -> None:
        self._change_threshold = change_threshold
        self._max_gap_seconds = max_gap_seconds
        self._last_ocr_frame: np.ndarray | None = None
        self._last_ocr_timestamp: float | None = None

    def should_ocr(self, roi_frame: np.ndarray, timestamp: float) -> bool:
        if self._last_ocr_frame is None:
            decision = True
        elif roi_frame.shape != self._last_ocr_frame.shape:
            # A shape change (e.g. ROI edited mid-run) is itself a state
            # change worth confirming.
            decision = True
        else:
            score = frame_difference_score(self._last_ocr_frame, roi_frame)
            gap = timestamp - self._last_ocr_timestamp
            decision = score > self._change_threshold or gap >= self._max_gap_seconds

        if decision:
            self._last_ocr_frame = roi_frame
            self._last_ocr_timestamp = timestamp
        return decision


class NaiveDenseOcrPolicy:
    """OCRs every single analyzed frame, unconditionally.

    Not the production default -- this exists only as a control/baseline
    to measure selective invocation's OCR-call reduction against
    (ROADMAP Milestone 4 acceptance gate 3), and must never be wired as
    the default pipeline policy.
    """

    def should_ocr(self, roi_frame: np.ndarray, timestamp: float) -> bool:
        return True
