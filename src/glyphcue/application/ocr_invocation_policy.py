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
    """The production selective policy with Temporal Transition Episode Detection:
    - OCR the first frame (to establish a baseline).
    - Uses cheap frame difference against the last-OCR'd baseline as candidate evidence.
    - When a visual change is detected, triggers an initial OCR call and opens a transition episode.
    - Suppresses redundant immediate OCR during unstable multi-frame visual transition bursts (e.g. cross-dissolves, scene cuts).
    - When the transition episode settles (consecutive frames stabilize), if the settled frame differs from the transition start, invokes OCR on the settled frame.
    - Periodic confirmation OCR is forced every `max_gap_seconds` when no change occurs.
    """

    def __init__(
        self,
        change_threshold: float = 0.02,
        max_gap_seconds: float = 2.0,
        stability_threshold: float = 0.015,
        min_transition_duration: float = 0.1,
        max_transition_seconds: float = 0.4,
    ) -> None:
        self._change_threshold = change_threshold
        self._max_gap_seconds = max_gap_seconds
        self._stability_threshold = stability_threshold
        self._min_transition_duration = min_transition_duration
        self._max_transition_seconds = max_transition_seconds

        self._last_ocr_frame: np.ndarray | None = None
        self._last_ocr_timestamp: float | None = None
        self._prev_frame: np.ndarray | None = None
        self._prev_timestamp: float | None = None

        self._in_transition: bool = False
        self._transition_start_timestamp: float | None = None
        self._transition_start_frame: np.ndarray | None = None

        self.last_trigger_reason: str | None = None
        self.last_difference_score: float | None = None
        self.transition_episodes: int = 0
        self.suppressed_candidate_triggers: int = 0

    def should_ocr(self, roi_frame: np.ndarray, timestamp: float) -> bool:
        if self._last_ocr_frame is None:
            self._last_ocr_frame = roi_frame
            self._last_ocr_timestamp = timestamp
            self._prev_frame = roi_frame
            self._prev_timestamp = timestamp
            self.last_trigger_reason = "first_frame"
            self.last_difference_score = None
            return True

        if roi_frame.shape != self._last_ocr_frame.shape:
            self._last_ocr_frame = roi_frame
            self._last_ocr_timestamp = timestamp
            self._prev_frame = roi_frame
            self._prev_timestamp = timestamp
            self._in_transition = False
            self.last_trigger_reason = "change_detected"
            self.last_difference_score = None
            return True

        diff_against_last_ocr = frame_difference_score(self._last_ocr_frame, roi_frame)
        consecutive_diff = (
            frame_difference_score(self._prev_frame, roi_frame)
            if self._prev_frame is not None and self._prev_frame.shape == roi_frame.shape
            else 0.0
        )

        decision = False
        reason = None

        if not self._in_transition:
            if diff_against_last_ocr <= self._change_threshold:
                gap = timestamp - (self._last_ocr_timestamp or 0.0)
                if gap >= self._max_gap_seconds:
                    decision, reason = True, "periodic_confirmation"
            else:
                # Visual change begins: OCR immediately and open transition episode
                decision, reason = True, "change_detected"
                self._in_transition = True
                self._transition_start_timestamp = timestamp
                self._transition_start_frame = roi_frame
        else:
            # Currently inside a transition episode
            transition_elapsed = timestamp - (self._transition_start_timestamp or timestamp)
            if transition_elapsed < self._min_transition_duration:
                # Still within minimum transition debounce window
                self.suppressed_candidate_triggers += 1
            elif consecutive_diff <= self._stability_threshold or transition_elapsed >= self._max_transition_seconds:
                # Episode settled!
                self._in_transition = False
                self.transition_episodes += 1
                # Check if settled frame differs from the transition start frame
                diff_against_trans_start = (
                    frame_difference_score(self._transition_start_frame, roi_frame)
                    if self._transition_start_frame is not None
                    else diff_against_last_ocr
                )
                if diff_against_trans_start > self._change_threshold:
                    decision, reason = True, "change_detected"
            else:
                # Still unstable / in burst
                self.suppressed_candidate_triggers += 1

        self._prev_frame = roi_frame
        self._prev_timestamp = timestamp

        if decision:
            self._last_ocr_frame = roi_frame
            self._last_ocr_timestamp = timestamp
            self.last_trigger_reason = reason
            self.last_difference_score = diff_against_last_ocr
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
