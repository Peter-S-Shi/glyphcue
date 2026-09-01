from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np

from glyphcue.adapters.pyav_media_source import PyAvMediaFrameSource, probe_media
from glyphcue.application.detector_assisted_signature import detector_assisted_signature
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.application.roi_crop import crop_to_roi
from glyphcue.application.visual_state_sampling import (
    SampledFrame,
    VisualStateGroup,
    group_visual_states,
)
from glyphcue.domain.roi import ROI

# Declared a priori for the whole Beta round, used unchanged for every
# fixture. The Beta signature is a normalized ink map, not the Alpha
# family's resolution-dependent edge mask, so it needs its own distance
# scale: identical text re-rendered across frames disagrees on only a
# few percent of ink cells (compression/anti-aliasing jitter after
# canonicalization), while genuinely different text disagrees on tens of
# percent.
BETA_GROUP_DISTANCE_THRESHOLD = 0.10

TextDetector = Callable[[np.ndarray], Any]


@dataclass
class BetaDryRunResult:
    """Result of one Detector-Assisted Beta dry run.

    Localization only -- recognition is never invoked, so
    `representative_*` is still a STAND-IN for the OCR calls a future
    selective policy WOULD make, plus (unlike the Alpha family) a real
    detector cost that has to be paid up front and is reported here so
    the gate can be judged on cost, not only on accuracy.
    """

    sampling_fps: float
    decoded_frame_count: int = 0
    sampled_frame_count: int = 0
    media_duration_seconds: float = 0.0
    elapsed_wall_seconds: float = 0.0
    detector_invocations: int = 0
    detector_wall_seconds: float = 0.0
    detector_cold_latency_seconds: float = 0.0
    detector_warm_mean_latency_seconds: float = 0.0
    detected_box_counts: list[int] = field(default_factory=list)
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
                "detector_invocations": self.detector_invocations,
                "detector_wall_seconds": round(self.detector_wall_seconds, 3),
                "detector_cold_latency_seconds": round(self.detector_cold_latency_seconds, 3),
                "detector_warm_mean_latency_seconds": round(
                    self.detector_warm_mean_latency_seconds, 3
                ),
                "media_duration_seconds": round(self.media_duration_seconds, 3),
                "elapsed_wall_seconds": round(self.elapsed_wall_seconds, 3),
                "max_representative_gap_seconds": round(self.max_representative_gap_seconds, 3),
            },
            "groups": [g.to_dict() for g in self.groups],
        }

    def format_report(self) -> str:
        return (
            "=== Detector-Assisted Beta Dry Run ===\n\n"
            f"Sampling Profile:            {self.sampling_fps:.1f} fps\n"
            f"Decoded Frames:               {self.decoded_frame_count}\n"
            f"Sampled Frames:               {self.sampled_frame_count}\n"
            f"Representatives (subtitle):   {self.representative_count}\n"
            f"Blank Groups:                 {self.blank_group_count}\n"
            f"Detector Invocations:         {self.detector_invocations}\n"
            f"Detector Wall Time:           {self.detector_wall_seconds:.2f}s\n"
            f"Detector Cold Latency:        {self.detector_cold_latency_seconds:.3f}s\n"
            f"Detector Warm Mean Latency:   {self.detector_warm_mean_latency_seconds:.3f}s\n"
            f"Media Duration:               {self.media_duration_seconds:.2f}s\n"
            f"Dry Run Elapsed Time:         {self.elapsed_wall_seconds:.2f}s\n"
            f"Max Representative Gap:       {self.max_representative_gap_seconds:.3f}s\n"
        )


def run_beta_detector_dry_run(
    path: Path,
    processing_range: ProcessingRange,
    roi: ROI,
    sampling_fps: float,
    detect: TextDetector,
    group_distance_threshold: float = BETA_GROUP_DISTANCE_THRESHOLD,
) -> BetaDryRunResult:
    """Detector-Assisted Beta dry run (M11 Research Gate):

        sampled ROI frames -> text DETECTION (localization only)
          -> glyph ink inside each detected caption line, canonicalized
          -> consecutive temporal grouping -> middle representative

    Reuses the same production decode/ROI-crop path and the same
    `visual_state_sampling.group_visual_states` grouping/representative
    harness as every Alpha round, so the only thing that changes is
    where the per-sample signature comes from.

    `detect` is injected (a callable taking one ROI-cropped frame and
    returning detector polygons) so this module never imports PaddleOCR
    and stays testable, and CI-runnable, without the heavy `[ocr]`
    extra. Recognition is never called. Nothing here is imported by
    production Path A job wiring or the UI.
    """
    if sampling_fps <= 0:
        raise ValueError("sampling_fps must be positive")

    metadata = probe_media(path)
    range_start, range_end = processing_range.resolve(metadata.duration_seconds)
    range_duration = max(0.0, range_end - range_start)

    result = BetaDryRunResult(sampling_fps=sampling_fps, media_duration_seconds=range_duration)
    sample_interval = 1.0 / sampling_fps
    next_sample_time = range_start

    detector_latencies: list[float] = []
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

            detector_start = time.monotonic()
            polygons = detect(roi_frame)
            detector_latencies.append(time.monotonic() - detector_start)

            polygons = list(polygons) if polygons is not None else []
            result.detected_box_counts.append(len(polygons))
            signature = detector_assisted_signature(roi_frame, polygons)

            sampled.append(
                SampledFrame(
                    index=result.sampled_frame_count,
                    timestamp=timestamp,
                    signature=signature,
                    # The detector, not a pixel-density threshold,
                    # decides blank: no detected text means no text.
                    is_blank=not polygons,
                )
            )
            result.sampled_frame_count += 1
            next_sample_time += sample_interval
    finally:
        source.close()
        result.elapsed_wall_seconds = time.monotonic() - wall_start

    result.detector_invocations = len(detector_latencies)
    result.detector_wall_seconds = float(sum(detector_latencies))
    if detector_latencies:
        result.detector_cold_latency_seconds = detector_latencies[0]
    if len(detector_latencies) > 1:
        result.detector_warm_mean_latency_seconds = float(np.mean(detector_latencies[1:]))

    grouping = group_visual_states(sampled, group_distance_threshold=group_distance_threshold)
    result.groups = grouping.groups
    return result
