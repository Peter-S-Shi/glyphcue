"""M11 Research Gate -- Hybrid Cascade cost gate.

Beta-S (7f72e1c) settled state IDENTITY: on the three frozen real
fixtures it holds 100% semantic transition recall with zero swallowed
states and 13/15/18 representatives, and it is the only glyph-evidence
rule that survives both background nuisances. What it did not settle is
COST: it pays one text-detector call per sampled frame -- 50 calls per
10s window at the frozen 5 fps evidence grid -- whether or not anything
on screen changed.

This module keeps Beta-S exactly as it is and changes only WHEN it runs.
The cheap, detector-free temporal evidence the Alpha family already
built (downsampled edge mask + per-pixel temporal persistence + oversized
component rejection, `subtitle_stable_signature`) becomes a SCHEDULER:

    every 5 fps grid point
      -> cheap signature (no detector)
      -> schedule?  candidate | candidate follow-up | sentinel
      -> only if scheduled: detector + Beta-S signature
    observed frames -> the frozen grouping/representative harness

Two properties are structural, not tuned, and both exist because the
Alpha family's own failure was over-trusting cheap evidence:

  * The cheap gate SCHEDULES, it never DECIDES. It cannot create,
    merge, or name a subtitle state; every semantic judgement is still
    made by Beta-S over detector-observed frames under the frozen 0.10
    threshold. A cheap false positive costs exactly one detector call.
  * The cheap gate can never permanently skip a stretch of video. A
    periodic safety sentinel forces an observation whenever the detector
    has not looked for `MAX_DETECTOR_GAP_SECONDS`, so "I saw no change"
    can delay the detector but never blind it. A cheap false negative
    therefore costs at most one sentinel period of latency, not a
    subtitle state.

Nothing here is imported by production Path A job wiring or the UI, and
recognition is never invoked.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np

from glyphcue.adapters.pyav_media_source import PyAvMediaFrameSource, probe_media
from glyphcue.application.beta_detector_dry_run import (
    BETA_GROUP_DISTANCE_THRESHOLD,
    TextDetector,
)
from glyphcue.application.beta_stroke_structural import beta_s_signature
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.application.roi_crop import crop_to_roi
from glyphcue.application.subtitle_stable_signature import (
    EdgeStabilityBuffer,
    downsampled_edge_mask,
    subtitle_stable_signature,
)
from glyphcue.application.visual_state_sampling import (
    _DEFAULT_GROUP_DISTANCE_THRESHOLD as ALPHA_GROUP_DISTANCE_THRESHOLD,
)
from glyphcue.application.visual_state_sampling import (
    SampledFrame,
    VisualStateGroup,
    group_visual_states,
    signature_distance,
)
from glyphcue.domain.roi import ROI

# Declared a priori for this round and used unchanged on every fixture.
#
# The cheap gate is deliberately MORE sensitive than the Alpha rule that
# once tried to decide states with this same evidence: a cheap false
# positive costs one detector call, a cheap false negative could cost a
# subtitle state. Half the Alpha grouping threshold is the recall-first
# side of a rule that already exists, not a new tunable -- it is derived
# from the frozen constant rather than searched.
CASCADE_CANDIDATE_DISTANCE_THRESHOLD = ALPHA_GROUP_DISTANCE_THRESHOLD / 2.0

# The detector must observe at least this often regardless of what the
# cheap gate believes. One second is chosen as a unit of subtitle
# lifetime -- burned-in captions are authored to be readable, so they are
# essentially never shorter -- rather than fitted to any fixture.
MAX_DETECTOR_GAP_SECONDS = 1.0

CheapSignature = Callable[[np.ndarray, EdgeStabilityBuffer], np.ndarray]


@dataclass
class HybridCascadeResult:
    """One cascade dry run.

    Accuracy fields mirror `BetaDryRunResult` exactly so the two are
    directly comparable; the cost fields are what this round adds --
    where each detector call came from, and what it replaced.
    """

    sampling_fps: float
    decoded_frame_count: int = 0
    sampled_frame_count: int = 0
    media_duration_seconds: float = 0.0
    elapsed_wall_seconds: float = 0.0
    cheap_gate_wall_seconds: float = 0.0
    detector_invocations: int = 0
    detector_wall_seconds: float = 0.0
    detector_cold_latency_seconds: float = 0.0
    detector_warm_mean_latency_seconds: float = 0.0
    observations: list[tuple[float, str]] = field(default_factory=list)
    groups: list[VisualStateGroup] = field(default_factory=list)

    @property
    def baseline_detector_invocations(self) -> int:
        """What Beta-S costs today: one detector call per sampled frame."""
        return self.sampled_frame_count

    @property
    def detector_call_reduction(self) -> float:
        if not self.sampled_frame_count:
            return 0.0
        return 1.0 - self.detector_invocations / self.sampled_frame_count

    @property
    def trigger_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for _timestamp, reason in self.observations:
            counts[reason] = counts.get(reason, 0) + 1
        return counts

    @property
    def max_detector_gap_seconds(self) -> float:
        """The longest the detector went without looking -- the number the
        safety sentinel exists to bound."""
        times = [t for t, _ in self.observations]
        if len(times) < 2:
            return 0.0
        return max(b - a for a, b in zip(times, times[1:]))

    @property
    def representative_timestamps(self) -> list[float]:
        return [g.representative_timestamp for g in self.groups if g.state_kind == "subtitle"]

    @property
    def representative_count(self) -> int:
        return len(self.representative_timestamps)

    @property
    def blank_group_count(self) -> int:
        return sum(1 for g in self.groups if g.state_kind == "blank")

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": {
                "sampling_fps": self.sampling_fps,
                "decoded_frame_count": self.decoded_frame_count,
                "sampled_frame_count": self.sampled_frame_count,
                "baseline_detector_invocations": self.baseline_detector_invocations,
                "detector_invocations": self.detector_invocations,
                "detector_call_reduction": round(self.detector_call_reduction, 3),
                "trigger_counts": self.trigger_counts,
                "max_detector_gap_seconds": round(self.max_detector_gap_seconds, 3),
                "representative_count": self.representative_count,
                "blank_group_count": self.blank_group_count,
                "detector_wall_seconds": round(self.detector_wall_seconds, 3),
                "cheap_gate_wall_seconds": round(self.cheap_gate_wall_seconds, 3),
                "elapsed_wall_seconds": round(self.elapsed_wall_seconds, 3),
                "media_duration_seconds": round(self.media_duration_seconds, 3),
            },
            "observations": [
                {"timestamp": round(t, 4), "trigger": reason} for t, reason in self.observations
            ],
            "groups": [g.to_dict() for g in self.groups],
        }


def run_hybrid_cascade_dry_run(
    path: Path,
    processing_range: ProcessingRange,
    roi: ROI,
    sampling_fps: float,
    detect: TextDetector,
    group_distance_threshold: float = BETA_GROUP_DISTANCE_THRESHOLD,
    signature_fn: Callable[[np.ndarray, Any], np.ndarray] = beta_s_signature,
    cheap_signature_fn: CheapSignature = subtitle_stable_signature,
    candidate_distance_threshold: float = CASCADE_CANDIDATE_DISTANCE_THRESHOLD,
    max_detector_gap_seconds: float = MAX_DETECTOR_GAP_SECONDS,
) -> HybridCascadeResult:
    """Beta-S state identity, scheduled instead of exhaustive.

    Reuses the production decode/ROI-crop path, the frozen 5 fps evidence
    grid, the Alpha-D cheap evidence, the Beta-S signature, and the same
    `group_visual_states` grouping/representative harness as every
    previous round -- so the ONLY thing that differs from a Beta-S run is
    which sampled frames the detector ever sees.

    `cheap_signature_fn` is injectable purely so tests can substitute a
    gate that is blind (never fires) or hysterical (always fires) and pin
    the two safety properties directly.
    """
    if sampling_fps <= 0:
        raise ValueError("sampling_fps must be positive")

    metadata = probe_media(path)
    range_start, range_end = processing_range.resolve(metadata.duration_seconds)
    result = HybridCascadeResult(
        sampling_fps=sampling_fps,
        media_duration_seconds=max(0.0, range_end - range_start),
    )

    sample_interval = 1.0 / sampling_fps
    next_sample_time = range_start
    stability = EdgeStabilityBuffer()

    cheap_anchor: np.ndarray | None = None
    last_observed_time: float | None = None
    force_next_observation = False

    detector_latencies: list[float] = []
    observed: list[SampledFrame] = []
    source = PyAvMediaFrameSource()
    source.open(path)
    wall_start = time.monotonic()
    try:
        for timestamp, frame in source.frames(range_start, range_end):
            result.decoded_frame_count += 1
            roi_frame = crop_to_roi(frame, roi)

            # The persistence buffer is fed at the video's NATIVE rate --
            # that is what makes "this edge held still" mean anything --
            # but it never invokes the detector, so it stays on the cheap
            # side of the cascade.
            cheap_start = time.monotonic()
            edge_mask = downsampled_edge_mask(roi_frame)
            stability.push(timestamp, edge_mask)
            result.cheap_gate_wall_seconds += time.monotonic() - cheap_start

            if timestamp < next_sample_time:
                continue
            next_sample_time += sample_interval
            result.sampled_frame_count += 1

            cheap_start = time.monotonic()
            cheap = cheap_signature_fn(edge_mask, stability)
            changed = cheap_anchor is None or (
                signature_distance(cheap, cheap_anchor) > candidate_distance_threshold
            )
            result.cheap_gate_wall_seconds += time.monotonic() - cheap_start

            if last_observed_time is None:
                reason = "bootstrap"
            elif force_next_observation:
                reason = "candidate_followup"
            elif changed:
                reason = "candidate"
            elif timestamp - last_observed_time >= max_detector_gap_seconds:
                reason = "sentinel"
            else:
                reason = None

            # A cheap trigger is evidence that something is IN PROGRESS,
            # and a transition renders across frames: the frame that
            # trips the gate may be mid-fade. Observing the next grid
            # point too costs one call and removes that whole class of
            # near-miss, which is the trade this round is willing to make.
            force_next_observation = reason == "candidate"

            if reason is None:
                continue

            detector_start = time.monotonic()
            polygons = detect(roi_frame)
            detector_latencies.append(time.monotonic() - detector_start)

            polygons = list(polygons) if polygons is not None else []
            observed.append(
                SampledFrame(
                    index=len(observed),
                    timestamp=timestamp,
                    signature=signature_fn(roi_frame, polygons),
                    is_blank=not polygons,
                )
            )
            result.observations.append((timestamp, reason))
            cheap_anchor = cheap
            last_observed_time = timestamp
    finally:
        source.close()
        result.elapsed_wall_seconds = time.monotonic() - wall_start

    result.detector_invocations = len(detector_latencies)
    result.detector_wall_seconds = float(sum(detector_latencies))
    if detector_latencies:
        result.detector_cold_latency_seconds = detector_latencies[0]
    if len(detector_latencies) > 1:
        result.detector_warm_mean_latency_seconds = float(np.mean(detector_latencies[1:]))

    result.groups = group_visual_states(
        observed,
        group_distance_threshold=group_distance_threshold,
        distance=signature_distance,
    ).groups
    return result
