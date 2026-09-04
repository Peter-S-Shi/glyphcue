from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from glyphcue.adapters.pyav_media_source import PyAvMediaFrameSource, probe_media
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.application.roi_crop import crop_to_roi
from glyphcue.application.visual_state_sampling import (
    SampledFrame,
    VisualStateGroup,
    group_visual_states,
    is_blank_signature,
    subtitle_visual_signature,
)
from glyphcue.domain.roi import ROI

_DEFAULT_GROUP_DISTANCE_THRESHOLD = 0.06
_DEFAULT_BLANK_DENSITY_THRESHOLD = 0.01
_DEFAULT_EDGE_THRESHOLD = 0.04


@dataclass
class AlphaDryRunResult:
    """Result of one bounded Alpha Dry-Run experiment run (M11 Research
    Gate, family A: practical frame sampling + cheap image dedup).

    Never invokes PaddleOCR or touches persistence -- `representative_*`
    fields are a STAND-IN for how many OCR calls a future selective
    policy built on this signature would make, not a real OCR-call count.
    """

    sampling_fps: float
    decoded_frame_count: int = 0
    sampled_frame_count: int = 0
    media_duration_seconds: float = 0.0
    elapsed_wall_seconds: float = 0.0
    groups: list[VisualStateGroup] = field(default_factory=list)

    @property
    def representative_timestamps(self) -> list[float]:
        return [g.representative_timestamp for g in self.groups if g.state_kind == "subtitle"]

    @property
    def representative_count(self) -> int:
        return len(self.representative_timestamps)

    @property
    def blank_group_count(self) -> int:
        return sum(1 for g in self.groups if g.state_kind == "blank")

    @property
    def max_representative_gap_seconds(self) -> float:
        """Worst-case span between one representative and the next -- the
        maximum boundary delay this profile could introduce before a
        real state change would be confirmed."""
        reps = self.representative_timestamps
        if len(reps) < 2:
            return 0.0
        return max(b - a for a, b in zip(reps, reps[1:]))

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": {
                "sampling_fps": self.sampling_fps,
                "decoded_frame_count": self.decoded_frame_count,
                "sampled_frame_count": self.sampled_frame_count,
                "representative_count": self.representative_count,
                "blank_group_count": self.blank_group_count,
                "media_duration_seconds": round(self.media_duration_seconds, 3),
                "elapsed_wall_seconds": round(self.elapsed_wall_seconds, 3),
                "max_representative_gap_seconds": round(self.max_representative_gap_seconds, 3),
            },
            "groups": [g.to_dict() for g in self.groups],
        }

    def format_report(self) -> str:
        return (
            "=== Alpha Visual-State Sampling Dry Run ===\n\n"
            f"Sampling Profile:            {self.sampling_fps:.1f} fps\n"
            f"Decoded Frames:               {self.decoded_frame_count}\n"
            f"Sampled Frames:               {self.sampled_frame_count}\n"
            f"Representatives (subtitle):   {self.representative_count}\n"
            f"Blank Groups:                 {self.blank_group_count}\n"
            f"Media Duration:               {self.media_duration_seconds:.2f}s\n"
            f"Dry Run Elapsed Time:         {self.elapsed_wall_seconds:.3f}s\n"
            f"Max Representative Gap:       {self.max_representative_gap_seconds:.3f}s\n"
        )


def run_alpha_visual_dry_run(
    path: Path,
    processing_range: ProcessingRange,
    roi: ROI,
    sampling_fps: float,
    group_distance_threshold: float = _DEFAULT_GROUP_DISTANCE_THRESHOLD,
    blank_density_threshold: float = _DEFAULT_BLANK_DENSITY_THRESHOLD,
    edge_threshold: float = _DEFAULT_EDGE_THRESHOLD,
) -> AlphaDryRunResult:
    """Bounded Alpha Dry-Run experiment (M11 Research Gate, family A):

        sampled ROI frames -> cheap subtitle-focused visual signature ->
        explicit blank state -> consecutive temporal visual-state
        grouping -> stable/middle representative

    Reuses the exact same production frame-decode / ROI-crop path as
    `trigger_replay.run_trigger_replay` (same `PyAvMediaFrameSource`,
    same `crop_to_roi`) so this experiment is evaluated against real
    decode/crop behavior, not a synthetic shortcut -- it just samples at
    a FIXED target fps instead of every decoded frame, and it never
    invokes PaddleOCR, persistence, or reconstruction. Entirely separate
    from `ChangeTriggeredOcrPolicy` / `OcrInvocationPolicy` and never
    imported by production job wiring (`ocr_evidence_job.py`,
    `multilingual_ocr_evidence_job.py`) -- an experimental profile-gated
    seam, not a change to the production invocation policy.
    """
    if sampling_fps <= 0:
        raise ValueError("sampling_fps must be positive")

    metadata = probe_media(path)
    range_start, range_end = processing_range.resolve(metadata.duration_seconds)
    range_duration = max(0.0, range_end - range_start)

    result = AlphaDryRunResult(sampling_fps=sampling_fps, media_duration_seconds=range_duration)
    sample_interval = 1.0 / sampling_fps
    next_sample_time = range_start

    sampled: list[SampledFrame] = []
    source = PyAvMediaFrameSource()
    source.open(path)
    wall_start = time.monotonic()
    try:
        for timestamp, frame in source.frames(range_start, range_end):
            result.decoded_frame_count += 1
            if timestamp < next_sample_time:
                continue

            roi_frame = crop_to_roi(frame, roi)
            signature = subtitle_visual_signature(roi_frame, edge_threshold=edge_threshold)
            sampled.append(
                SampledFrame(
                    index=result.sampled_frame_count,
                    timestamp=timestamp,
                    signature=signature,
                    is_blank=is_blank_signature(
                        signature, density_threshold=blank_density_threshold
                    ),
                )
            )
            result.sampled_frame_count += 1
            next_sample_time += sample_interval
    finally:
        source.close()
        result.elapsed_wall_seconds = time.monotonic() - wall_start

    grouping = group_visual_states(sampled, group_distance_threshold=group_distance_threshold)
    result.groups = grouping.groups
    return result
