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
        self.last_trigger_reason: str | None = None
        """Why the most recent `should_ocr()` call that returned True
        did so -- "first_frame", "change_detected", or
        "periodic_confirmation". Unchanged by calls that return False.
        Not part of the `OcrInvocationPolicy` Protocol (an optional,
        duck-typed extra `build_ocr_evidence_job` reads via getattr()
        when present) -- M5's multi-frame consensus uses this as real,
        already-computed evidence for genuine state-change boundaries,
        instead of guessing them from OCR text similarity alone."""

    def should_ocr(self, roi_frame: np.ndarray, timestamp: float) -> bool:
        if self._last_ocr_frame is None:
            decision, reason = True, "first_frame"
        elif roi_frame.shape != self._last_ocr_frame.shape:
            # A shape change (e.g. ROI edited mid-run) is itself a state
            # change worth confirming.
            decision, reason = True, "change_detected"
        else:
            score = frame_difference_score(self._last_ocr_frame, roi_frame)
            gap = timestamp - self._last_ocr_timestamp
            if score > self._change_threshold:
                decision, reason = True, "change_detected"
            elif gap >= self._max_gap_seconds:
                decision, reason = True, "periodic_confirmation"
            else:
                decision, reason = False, None

        if decision:
            self._last_ocr_frame = roi_frame
            self._last_ocr_timestamp = timestamp
            self.last_trigger_reason = reason
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
