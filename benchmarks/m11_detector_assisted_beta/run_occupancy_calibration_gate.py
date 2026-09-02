"""M11 Research Gate -- occupancy-normalized distance: invariance + calibration.

Two questions, one run, research-only. Nothing here touches production:
the production path still uses `signature_distance` and the frozen 0.10.

1. INVARIANCE. `signature_distance` divides the cell mismatch by the whole
   fixed MAX_LINES canvas, so bands no line was detected in contribute
   zeros to both operands and only dilute the result -- which makes the
   measured distance scale with how many bands the detector happened to
   fill. A user drawing their ROI tighter can crop away the second line
   of a two-line caption and halve every distance in the run. This
   replays the same window under one frozen ROI and seven systematic
   perturbations of it and prints both metrics side by side, so the
   scaling (or its absence) is directly visible.

2. CALIBRATION. Because the occupancy-normalized denominator is smaller,
   distances under it are larger and the frozen 0.10 operating point does
   not carry over. The rule below re-derives one -- or refuses to.

   THE RULE, declared before it was ever run and applied exactly once:

     * calibrate on sample_d only (the problematic fixture) plus its ROI
       perturbations; sample_a and sample_b are held back for validation;
     * use only observations that fall inside a ground-truth state span
       AND outside every declared transition window, so frames caught
       mid-crossfade cannot pollute either distribution;
     * S = max over same-state pairwise distances;
       D = min over ADJACENT different-state pairwise distances;
     * if D > S, the threshold is sqrt(S * D) -- the scale-free midpoint
       of the gap, which maximizes the multiplicative margin to both
       bounds for a ratio-scaled metric -- rounded to three decimals and
       then FROZEN;
     * if D <= S there is no stable positive discriminability margin:
       STOP and report. Do not search, and do not substitute a different
       rule after seeing the numbers.

Requires the `[ocr]` extra (detection only, no recognition):
    python -m benchmarks.m11_detector_assisted_beta.run_occupancy_calibration_gate
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from glyphcue.adapters.pyav_media_source import PyAvMediaFrameSource
from glyphcue.application.beta_stroke_structural import beta_s_signature
from glyphcue.application.detector_assisted_signature import (
    MAX_LINES,
    detected_lines_from_polygons,
)
from glyphcue.application.hybrid_cascade_dry_run import (
    CASCADE_CANDIDATE_DISTANCE_THRESHOLD,
    MAX_DETECTOR_GAP_SECONDS,
)
from glyphcue.application.occupancy_normalized_distance import (
    occupancy_normalized_distance,
)
from glyphcue.application.roi_crop import crop_to_roi
from glyphcue.application.subtitle_stable_signature import (
    EdgeStabilityBuffer,
    downsampled_edge_mask,
    subtitle_stable_signature,
)
from glyphcue.application.text_anchored_region_mask import TextAnchoredRegionMask
from glyphcue.application.visual_state_sampling import signature_distance
from glyphcue.domain.roi import ROI

from benchmarks.m11_detector_assisted_beta.paddle_text_detector import PaddleTextDetector
from benchmarks.m11_detector_assisted_beta.run_beta_dry_run import (
    _CORPUS_DIR,
    _FROZEN_SAMPLING_FPS,
)

_GROUND_TRUTH = "sample_d_alpha_window_ground_truth.json"

# One perturbation family, applied unchanged: (shift as a fraction of the
# ROI's own height, height scale). "hand_drawn_tight" is the real ROI a
# user drew, the one the whole corrective-hardening thread started from.
_ROI_VARIANTS = {
    "frozen": (0.0, 1.00),
    "hand_drawn_tight": (0.17, 0.60),
    "tight_070": (0.15, 0.70),
    "tight_085": (0.075, 0.85),
    "loose_120": (-0.10, 1.20),
    "loose_140": (-0.20, 1.40),
    "shift_down": (0.08, 1.00),
    "shift_up": (-0.08, 1.00),
}


def _variant_roi(base: tuple[float, ...], shift: float, scale: float) -> ROI:
    x, y, width, height = base
    top = max(0.0, y + height * shift)
    bottom = min(1.0, top + height * scale)
    return ROI(x, top, width, bottom - top)


def _observe_window(detector, path: Path, roi: ROI, window: tuple[float, float]):
    """Replays the frozen hybrid scheduler and returns what it observed.

    The scheduler is untouched here -- its decisions depend only on the
    detector and the region mask, never on the distance metric, so the
    observation sequence is the same one production would collect.
    """
    region_mask = TextAnchoredRegionMask()
    stability = EdgeStabilityBuffer()
    interval = 1.0 / _FROZEN_SAMPLING_FPS
    next_sample = window[0]
    cheap_anchor = None
    last_observed: float | None = None
    force_next = False
    pending = None
    observations: list[dict[str, Any]] = []

    def observe(timestamp, roi_frame, edge_mask):
        nonlocal cheap_anchor
        polygons = [np.asarray(p, dtype=np.float64) for p in (detector(roi_frame) or [])]
        region_mask.update(polygons, roi_frame.shape[:2])
        cheap_anchor = region_mask.apply(subtitle_stable_signature(edge_mask, stability))
        observations.append(
            {
                "timestamp": timestamp,
                "signature": beta_s_signature(roi_frame, polygons),
                "lines": len(detected_lines_from_polygons(polygons)[:MAX_LINES]),
            }
        )

    source = PyAvMediaFrameSource()
    source.open(path)
    try:
        for timestamp, frame in source.frames(*window):
            roi_frame = crop_to_roi(frame, roi)
            edge_mask = downsampled_edge_mask(roi_frame)
            stability.push(timestamp, edge_mask)
            if timestamp < next_sample:
                continue
            next_sample += interval
            cheap = region_mask.apply(subtitle_stable_signature(edge_mask, stability))
            changed = cheap_anchor is None or (
                signature_distance(cheap, cheap_anchor) > CASCADE_CANDIDATE_DISTANCE_THRESHOLD
            )
            if last_observed is None:
                reason = "bootstrap"
            elif force_next:
                reason = "candidate_followup"
            elif changed:
                reason = "candidate"
            elif timestamp - last_observed >= MAX_DETECTOR_GAP_SECONDS:
                reason = "sentinel"
            else:
                reason = None
            force_next = reason == "candidate"
            if reason is None:
                pending = (timestamp, roi_frame, edge_mask)
            else:
                pending = None
                observe(timestamp, roi_frame, edge_mask)
                last_observed = timestamp
    finally:
        source.close()
    if pending is not None:
        observe(*pending)
    return observations


def _calibration_label(timestamp: float, states, transitions) -> int | None:
    for low, high in transitions:
        if low <= timestamp <= high:
            return None
    for index, (low, high) in enumerate(states):
        if low <= timestamp <= high:
            return index
    return None


def run() -> dict[str, Any] | None:
    ground_truth = _CORPUS_DIR / _GROUND_TRUTH
    if not ground_truth.exists():
        print(
            "M11 occupancy calibration gate skipped: private corpus / "
            "ground-truth files not present on this machine. Safe to run "
            "without them."
        )
        return None

    data = json.loads(ground_truth.read_text(encoding="utf-8"))
    video = _CORPUS_DIR / data["video_path"]
    if not video.exists():
        print("M11 occupancy calibration gate skipped: private corpus absent.")
        return None

    base_roi = tuple(data["roi"])
    window = (data["window_start_seconds"], data["window_end_seconds"])
    states = [(s["start_seconds"], s["end_seconds"]) for s in data["states"]]
    transitions = [tuple(t["window"]) for t in data["transitions"]]

    detector = PaddleTextDetector()
    detector.initialize()
    same: list[float] = []
    different: list[float] = []
    try:
        print("=== occupancy invariance: mean pairwise distance per ROI variant ===")
        print(f"{'variant':18s}{'lines':>7s}{'production':>12s}{'occupancy':>11s}")
        for variant, (shift, scale) in _ROI_VARIANTS.items():
            roi = _variant_roi(base_roi, shift, scale)
            observations = _observe_window(detector, video, roi, window)
            signatures = [o["signature"] for o in observations]
            pairs = [
                (i, j)
                for i in range(len(signatures))
                for j in range(i + 1, len(signatures))
            ]
            production = [signature_distance(signatures[i], signatures[j]) for i, j in pairs]
            occupancy = [
                occupancy_normalized_distance(signatures[i], signatures[j]) for i, j in pairs
            ]
            print(
                f"{variant:18s}{float(np.mean([o['lines'] for o in observations])):7.2f}"
                f"{float(np.mean(production)):12.4f}{float(np.mean(occupancy)):11.4f}"
            )

            labels = [
                _calibration_label(o["timestamp"], states, transitions) for o in observations
            ]
            for (i, j), distance in zip(pairs, occupancy):
                first, second = labels[i], labels[j]
                if first is None or second is None:
                    continue
                if first == second:
                    same.append(distance)
                elif abs(first - second) == 1:
                    different.append(distance)
    finally:
        detector.shutdown()

    print(
        f"\n=== calibration ({len(same)} same-state pairs, "
        f"{len(different)} adjacent different-state pairs) ==="
    )
    for name, values in (("same-state within", same), ("different-state", different)):
        array = np.asarray(values)
        print(
            f"  {name:20s} min={array.min():.4f} p50={np.median(array):.4f} "
            f"p95={np.quantile(array, 0.95):.4f} max={array.max():.4f}"
        )

    upper, lower = max(same), min(different)
    print(f"\nS = max(same-state)      = {upper:.4f}")
    print(f"D = min(different-state) = {lower:.4f}")
    if lower > upper:
        threshold = round(math.sqrt(upper * lower), 3)
        print(f"POSITIVE GAP -> threshold = sqrt(S*D) = {threshold} (FROZEN)")
        return {"stopped": False, "S": upper, "D": lower, "threshold": threshold}

    print(
        "NO POSITIVE GAP -> STOP. No threshold is derived and none is "
        "searched; substituting a different rule now would be fitting the "
        "rule to the numbers."
    )
    print(
        f"  overlap band [{lower:.4f}, {upper:.4f}]: "
        f"{sum(1 for value in same if value >= lower)}/{len(same)} same-state "
        f"pairs at or above D, "
        f"{sum(1 for value in different if value <= upper)}/{len(different)} "
        f"different-state pairs at or below S"
    )
    return {"stopped": True, "S": upper, "D": lower, "threshold": None}


if __name__ == "__main__":
    run()
