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
    """The production selective policy with Deferred OCR Confirmation & Temporal Transition Episode Detection:
    - Holds the pre-episode confirmed OCR baseline fixed while temporal evidence accumulates.
    - Low `change_threshold` acts as a cheap candidate-onset signal only; it does NOT immediately invoke OCR.
    - Suppresses OCR throughout an unstable transition burst (e.g. cross-dissolves, scene cuts).
    - When the episode settles, evaluates whether the settled state has a confirmed difference against the fixed baseline.
    - If confirmed, invokes OCR ONCE on the stable representative frame and updates the confirmed baseline.
    - Discards transient spikes and low-amplitude background noise without invoking OCR.
    - Forces periodic confirmation OCR every `max_gap_seconds` when no change occurs.
    """

    def __init__(
        self,
        change_threshold: float = 0.02,
        confirmation_threshold: float = 0.02,
        stability_threshold: float = 0.015,
        min_stable_frames: int = 1,
        min_episode_duration: float = 0.033,
        max_transition_seconds: float = 0.35,
        max_gap_seconds: float = 2.0,
    ) -> None:
        self._change_threshold = change_threshold
        self._confirmation_threshold = confirmation_threshold
        self._stability_threshold = stability_threshold
        self._min_stable_frames = min_stable_frames
        self._min_episode_duration = min_episode_duration
        self._max_transition_seconds = max_transition_seconds
        self._max_gap_seconds = max_gap_seconds

        self._confirmed_ocr_frame: np.ndarray | None = None
        self._confirmed_ocr_timestamp: float | None = None
        self._prev_frame: np.ndarray | None = None
        self._prev_timestamp: float | None = None

        self._candidate_episode_active: bool = False
        self._candidate_start_timestamp: float | None = None
        self._stable_run_count: int = 0

        self.last_trigger_reason: str | None = None
        self.last_difference_score: float | None = None
        self.candidate_transition_episodes: int = 0
        self.confirmed_transition_episodes: int = 0
        self.suppressed_candidate_triggers: int = 0

    @property
    def transition_episodes(self) -> int:
        """Alias for confirmed_transition_episodes for diagnostics compatibility."""
        return self.confirmed_transition_episodes

    def should_ocr(self, roi_frame: np.ndarray, timestamp: float) -> bool:
        if self._confirmed_ocr_frame is None:
            self._confirmed_ocr_frame = roi_frame
            self._confirmed_ocr_timestamp = timestamp
            self._prev_frame = roi_frame
            self._prev_timestamp = timestamp
            self.last_trigger_reason = "first_frame"
            self.last_difference_score = None
            return True

        if roi_frame.shape != self._confirmed_ocr_frame.shape:
            self._confirmed_ocr_frame = roi_frame
            self._confirmed_ocr_timestamp = timestamp
            self._prev_frame = roi_frame
            self._prev_timestamp = timestamp
            self._candidate_episode_active = False
            self.last_trigger_reason = "change_detected"
            self.last_difference_score = None
            self.confirmed_transition_episodes += 1
            return True

        diff_against_confirmed = frame_difference_score(self._confirmed_ocr_frame, roi_frame)
        consecutive_diff = (
            frame_difference_score(self._prev_frame, roi_frame)
            if self._prev_frame is not None and self._prev_frame.shape == roi_frame.shape
            else 0.0
        )

        decision = False
        reason = None

        if not self._candidate_episode_active:
            if diff_against_confirmed <= self._change_threshold:
                gap = timestamp - (self._confirmed_ocr_timestamp or 0.0)
                if gap >= self._max_gap_seconds:
                    decision, reason = True, "periodic_confirmation"
                    self._confirmed_ocr_frame = roi_frame
                    self._confirmed_ocr_timestamp = timestamp
                    self.last_trigger_reason = reason
                    self.last_difference_score = diff_against_confirmed
            else:
                # Candidate onset: do NOT invoke OCR immediately; hold confirmed baseline fixed
                self._candidate_episode_active = True
                self._candidate_start_timestamp = timestamp
                self.candidate_transition_episodes += 1
                self.suppressed_candidate_triggers += 1
                self._stable_run_count = 1 if consecutive_diff <= self._stability_threshold else 0
        else:
            # Candidate episode in progress
            if diff_against_confirmed <= self._change_threshold:
                # Reverted to confirmed baseline (transient spike / noise)
                self._candidate_episode_active = False
                self._stable_run_count = 0
            else:
                if consecutive_diff <= self._stability_threshold:
                    self._stable_run_count += 1
                else:
                    self._stable_run_count = 0

                elapsed_in_episode = timestamp - (self._candidate_start_timestamp or timestamp)
                is_settled = (
                    self._stable_run_count >= self._min_stable_frames
                    and elapsed_in_episode >= (self._min_episode_duration - 1e-4)
                ) or (elapsed_in_episode >= self._max_transition_seconds)

                if is_settled:
                    self._candidate_episode_active = False
                    self._stable_run_count = 0
                    settled_diff = frame_difference_score(self._confirmed_ocr_frame, roi_frame)
                    if settled_diff >= self._confirmation_threshold:
                        decision, reason = True, "change_detected"
                        self.confirmed_transition_episodes += 1
                        self._confirmed_ocr_frame = roi_frame
                        self._confirmed_ocr_timestamp = timestamp
                        self.last_trigger_reason = reason
                        self.last_difference_score = settled_diff
                else:
                    self.suppressed_candidate_triggers += 1

        self._prev_frame = roi_frame
        self._prev_timestamp = timestamp
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
