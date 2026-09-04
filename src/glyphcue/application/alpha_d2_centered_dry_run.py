from __future__ import annotations

import time
from pathlib import Path

from glyphcue.adapters.pyav_media_source import PyAvMediaFrameSource, probe_media
from glyphcue.application.alpha_visual_dry_run import AlphaDryRunResult
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.application.roi_crop import crop_to_roi
from glyphcue.application.subtitle_stable_signature import (
    CenteredEdgeStabilityIndex,
    combine_signature,
    downsampled_edge_mask,
)
from glyphcue.application.visual_state_sampling import (
    SampledFrame,
    group_visual_states,
    is_blank_signature,
)
from glyphcue.domain.roi import ROI

# Deliberately IDENTICAL to alpha_d_stable_dry_run.py's constants -- this
# experiment tests only WHERE persistence evidence comes from (centered
# vs. causal-trailing), never a new number tuned against any fixture.
from glyphcue.application.alpha_d_stable_dry_run import (
    _DEFAULT_BLANK_DENSITY_THRESHOLD,
    _DEFAULT_EDGE_THRESHOLD,
    _DEFAULT_GROUP_DISTANCE_THRESHOLD,
    _DEFAULT_MAX_COMPONENT_FRACTION,
    _DEFAULT_PERSISTENCE_THRESHOLD,
    _DEFAULT_STABILITY_WINDOW_SECONDS,
)


def run_alpha_d2_centered_dry_run(
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
    """Alpha-D2 structural corrective (M11 Research Gate): identical to
    `alpha_d_stable_dry_run.run_alpha_d_stable_dry_run` -- same edge
    extraction, same persistence THRESHOLD and evidence HORIZON, same
    connected-component filter, same blank/group thresholds, same
    sampling -> grouping -> representative harness
    (`visual_state_sampling.group_visual_states`, the same
    `AlphaDryRunResult` shape) -- except the persistence evidence itself
    comes from `CenteredEdgeStabilityIndex` (backward AND forward within
    the SAME total horizon) instead of `EdgeStabilityBuffer` (backward
    only).

    This targets one specific, previously-identified structural failure
    mode: a purely causal trailing window has no evidence yet from a
    brand-new subtitle state at the exact moment it begins, so the first
    sample(s) after a real transition can score "unstable" even though
    the state is genuinely about to hold -- a short-lived spurious extra
    group right at onset (`docs` note in 389fad0's commit message; also
    reproduced on the non-private `difficult_noisy_background` fixture).
    Centering the same horizon lets an onset frame also see its own
    state's near-future frames.

    Two-pass (decode everything in the processing range first, THEN
    sample) instead of Alpha-D's single streaming pass, because a
    centered/look-ahead window needs frames that come chronologically
    AFTER a given sample -- valid only because GlyphCue Path A OCR is
    offline batch processing over an already fully-available video file,
    never a live/real-time stream. Still no PaddleOCR, no detector, no
    tracking; still not imported by any production job or UI wiring.
    """
    if sampling_fps <= 0:
        raise ValueError("sampling_fps must be positive")

    metadata = probe_media(path)
    range_start, range_end = processing_range.resolve(metadata.duration_seconds)
    range_duration = max(0.0, range_end - range_start)

    result = AlphaDryRunResult(sampling_fps=sampling_fps, media_duration_seconds=range_duration)

    source = PyAvMediaFrameSource()
    source.open(path)
    wall_start = time.monotonic()
    try:
        decoded_entries: list[tuple[float, "object"]] = []
        for timestamp, frame in source.frames(range_start, range_end):
            result.decoded_frame_count += 1
            roi_frame = crop_to_roi(frame, roi)
            edge_mask = downsampled_edge_mask(roi_frame, edge_threshold=edge_threshold)
            decoded_entries.append((timestamp, edge_mask))
    finally:
        source.close()

    stability_index = CenteredEdgeStabilityIndex(decoded_entries, window_seconds=stability_window_seconds)

    sample_interval = 1.0 / sampling_fps
    next_sample_time = range_start
    sampled: list[SampledFrame] = []
    for timestamp, edge_mask in decoded_entries:
        if timestamp < next_sample_time:
            continue

        persistence = stability_index.persistence_ratio(timestamp)
        signature = combine_signature(
            edge_mask,
            persistence,
            persistence_threshold=persistence_threshold,
            max_component_fraction=max_component_fraction,
        )
        sampled.append(
            SampledFrame(
                index=result.sampled_frame_count,
                timestamp=timestamp,
                signature=signature,
                is_blank=is_blank_signature(signature, density_threshold=blank_density_threshold),
            )
        )
        result.sampled_frame_count += 1
        next_sample_time += sample_interval

    result.elapsed_wall_seconds = time.monotonic() - wall_start

    grouping = group_visual_states(sampled, group_distance_threshold=group_distance_threshold)
    result.groups = grouping.groups
    return result
