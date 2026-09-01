from __future__ import annotations

import time
from pathlib import Path

from glyphcue.adapters.pyav_media_source import PyAvMediaFrameSource, probe_media
from glyphcue.application.alpha_visual_dry_run import AlphaDryRunResult
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.application.roi_crop import crop_to_roi
from glyphcue.application.subtitle_stable_signature import (
    EdgeStabilityBuffer,
    downsampled_edge_mask,
    subtitle_stable_signature,
)
from glyphcue.application.visual_state_sampling import (
    SampledFrame,
    group_visual_states,
    is_blank_signature,
)
from glyphcue.domain.roi import ROI

_DEFAULT_GROUP_DISTANCE_THRESHOLD = 0.06
_DEFAULT_EDGE_THRESHOLD = 0.04
_DEFAULT_STABILITY_WINDOW_SECONDS = 0.4
_DEFAULT_PERSISTENCE_THRESHOLD = 0.6
_DEFAULT_MAX_COMPONENT_FRACTION = 0.12
# The filtered signature is much sparser than the raw whole-ROI edge
# mask it replaces (edge+persistence+component filtering removes most
# of a talking-head ROI's edge content by design), so "blank" has to be
# judged on a correspondingly smaller density -- a structural adaptation
# to the new signal's scale, fixed a priori, not tuned against any one
# fixture's pass/fail outcome.
_DEFAULT_BLANK_DENSITY_THRESHOLD = 0.002


def run_alpha_d_stable_dry_run(
    path: Path,
    processing_range: ProcessingRange,
    roi: ROI,
    sampling_fps: float,
    stability_window_seconds: float = _DEFAULT_STABILITY_WINDOW_SECONDS,
    persistence_threshold: float = _DEFAULT_PERSISTENCE_THRESHOLD,
    max_component_fraction: float = _DEFAULT_MAX_COMPONENT_FRACTION,
    group_distance_threshold: float = _DEFAULT_GROUP_DISTANCE_THRESHOLD,
    blank_density_threshold: float = _DEFAULT_BLANK_DENSITY_THRESHOLD,
    edge_threshold: float = _DEFAULT_EDGE_THRESHOLD,
) -> AlphaDryRunResult:
    """Alpha-D corrective experiment (M11 Research Gate): same sampling
    -> grouping -> representative harness as
    `alpha_visual_dry_run.run_alpha_visual_dry_run` (reuses
    `visual_state_sampling.group_visual_states` and the same
    `AlphaDryRunResult` shape unchanged), but the per-sample signature is
    replaced with `subtitle_stable_signature.subtitle_stable_signature`
    -- edge presence AND short-window temporal persistence AND
    connected-component size filtering -- instead of the raw whole-ROI
    edge mask that commit 973157b showed was dominated by ordinary human
    motion.

    The stability buffer is fed EVERY natively decoded frame (not just
    sampled ones), because persistence is a claim about the real video's
    motion at native frame rate; only sampling and grouping stay fixed
    at `sampling_fps`. Still the same production decode/ROI-crop path
    (`PyAvMediaFrameSource`, `crop_to_roi`); still no PaddleOCR, no
    detector, no tracking; still not imported by any production job or
    UI wiring.
    """
    if sampling_fps <= 0:
        raise ValueError("sampling_fps must be positive")

    metadata = probe_media(path)
    range_start, range_end = processing_range.resolve(metadata.duration_seconds)
    range_duration = max(0.0, range_end - range_start)

    result = AlphaDryRunResult(sampling_fps=sampling_fps, media_duration_seconds=range_duration)
    sample_interval = 1.0 / sampling_fps
    next_sample_time = range_start

    stability = EdgeStabilityBuffer(window_seconds=stability_window_seconds)
    sampled: list[SampledFrame] = []
    source = PyAvMediaFrameSource()
    source.open(path)
    wall_start = time.monotonic()
    try:
        for timestamp, frame in source.frames(range_start, range_end):
            result.decoded_frame_count += 1
            roi_frame = crop_to_roi(frame, roi)
            edge_mask = downsampled_edge_mask(roi_frame, edge_threshold=edge_threshold)
            stability.push(timestamp, edge_mask)

            if timestamp < next_sample_time:
                continue

            signature = subtitle_stable_signature(
                edge_mask,
                stability,
                persistence_threshold=persistence_threshold,
                max_component_fraction=max_component_fraction,
            )
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
