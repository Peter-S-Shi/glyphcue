from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from glyphcue.adapters.pyav_media_source import PyAvMediaFrameSource, probe_media
from glyphcue.application.ocr_invocation_policy import (
    ChangeTriggeredOcrPolicy,
    OcrInvocationPolicy,
)
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.application.roi_crop import crop_to_roi
from glyphcue.domain.roi import ROI


@dataclass(frozen=True)
class TriggerDecisionRecord:
    timestamp: float
    trigger_reason: str
    difference_score: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": round(self.timestamp, 4),
            "trigger_reason": self.trigger_reason,
            "difference_score": (
                round(self.difference_score, 4)
                if self.difference_score is not None
                else None
            ),
        }


@dataclass
class TriggerReplayResult:
    frames_analyzed: int = 0
    decided_ocr_calls: int = 0
    candidate_transition_episodes: int = 0
    confirmed_transition_episodes: int = 0
    suppressed_candidate_triggers: int = 0
    media_duration_seconds: float = 0.0
    elapsed_wall_seconds: float = 0.0
    decisions: list[TriggerDecisionRecord] = field(default_factory=list)

    @property
    def effective_fps(self) -> float:
        if self.elapsed_wall_seconds <= 0:
            return 0.0
        return self.frames_analyzed / self.elapsed_wall_seconds

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": {
                "frames_analyzed": self.frames_analyzed,
                "decided_ocr_calls": self.decided_ocr_calls,
                "candidate_transition_episodes": self.candidate_transition_episodes,
                "confirmed_transition_episodes": self.confirmed_transition_episodes,
                "suppressed_candidate_triggers": self.suppressed_candidate_triggers,
                "media_duration_seconds": round(self.media_duration_seconds, 3),
                "elapsed_wall_seconds": round(self.elapsed_wall_seconds, 3),
                "effective_fps": round(self.effective_fps, 2),
            },
            "decisions": [d.to_dict() for d in self.decisions],
        }

    def format_report(self) -> str:
        triggers: dict[str, int] = {}
        for d in self.decisions:
            triggers[d.trigger_reason] = triggers.get(d.trigger_reason, 0) + 1
        triggers_str = ", ".join(f"{k}: {v}" for k, v in sorted(triggers.items())) or "none"

        return (
            "=== Trigger Replay Report (Dry Run) ===\n\n"
            f"Frames Analyzed:            {self.frames_analyzed}\n"
            f"Decided OCR Calls:          {self.decided_ocr_calls}\n"
            f"Candidate Episodes:         {self.candidate_transition_episodes}\n"
            f"Confirmed Episodes:         {self.confirmed_transition_episodes}\n"
            f"Suppressed Triggers:        {self.suppressed_candidate_triggers}\n"
            f"Media Duration:             {self.media_duration_seconds:.2f}s\n"
            f"Dry Run Elapsed Time:       {self.elapsed_wall_seconds:.3f}s ({self.effective_fps:.1f} fps)\n\n"
            "--- Decided Triggers ---\n"
            f"{triggers_str}\n"
        )


def run_trigger_replay(
    path: Path,
    processing_range: ProcessingRange,
    roi: ROI,
    policy: OcrInvocationPolicy | None = None,
) -> TriggerReplayResult:
    """Rapid, local-first Dry Run that runs production frame decoding and ROI cropping
    through the OCR invocation policy without invoking the expensive OCR engine or persisting to SQLite.
    """
    active_policy = policy if policy is not None else ChangeTriggeredOcrPolicy()
    metadata = probe_media(path)
    range_start, range_end = processing_range.resolve(metadata.duration_seconds)
    range_duration = max(0.0, range_end - range_start)

    result = TriggerReplayResult(media_duration_seconds=range_duration)
    source = PyAvMediaFrameSource()
    source.open(path)
    wall_start = time.monotonic()
    try:
        for timestamp, frame in source.frames(range_start, range_end):
            result.frames_analyzed += 1
            roi_frame = crop_to_roi(frame, roi)
            if active_policy.should_ocr(roi_frame, timestamp):
                result.decided_ocr_calls += 1
                reason = getattr(active_policy, "last_trigger_reason", "unspecified")
                diff_score = getattr(active_policy, "last_difference_score", None)
                result.decisions.append(
                    TriggerDecisionRecord(
                        timestamp=timestamp,
                        trigger_reason=reason,
                        difference_score=diff_score,
                    )
                )
    finally:
        source.close()
        result.elapsed_wall_seconds = time.monotonic() - wall_start
        result.candidate_transition_episodes = getattr(
            active_policy, "candidate_transition_episodes", 0
        )
        result.confirmed_transition_episodes = getattr(
            active_policy, "confirmed_transition_episodes", 0
        )
        result.suppressed_candidate_triggers = getattr(
            active_policy, "suppressed_candidate_triggers", 0
        )

    return result
