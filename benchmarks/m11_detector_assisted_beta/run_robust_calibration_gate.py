"""M11 Research Gate -- robust calibration policy + held-out validation.

Research-only. Production keeps `signature_distance` and the frozen 0.10
regardless of what this prints.

The hard-bound rule (max same-state vs min different-state) was honestly
exhausted in `run_occupancy_calibration_gate`: after a full
threshold-independent audit of every ground-truth boundary the bounds
still crossed, and the audit proved that overlap is a real tail overlap
between within-state drift and between-state similarity rather than
label contamination. So this gate replaces the BOUNDS with QUANTILES --
once, declared in advance:

  CALIBRATION POLICY, frozen before this file was ever run:
    * calibrate on sample_d and its existing ROI perturbation family
      only; sample_a and sample_b are held out and are not consulted
      while deriving anything;
    * S95 = p95 of same-state pairwise occupancy-normalized distances;
      D05 = p05 of adjacent different-state pairwise distances;
    * if D05 > S95 the threshold is sqrt(S95 * D05), rounded to three
      decimals (the precision rule already used for this metric) and
      immediately frozen; otherwise STOP;
    * no grid search, no re-choosing the quantiles afterwards, and no
      revisiting the policy after seeing held-out results.

  HELD-OUT VALIDATION then runs the frozen metric and frozen threshold
  unchanged over sample_a, sample_b and their ROI perturbations, plus
  sample_d's own frozen and real hand-drawn ROI. Grouping topology is
  untouched -- same anchor-based grouper, same medoid representative,
  same scheduler-produced observations. Any held-out failure is a STOP;
  the threshold may not be adjusted to accommodate it.

Requires the `[ocr]` extra (detection only, no recognition):
    python -m benchmarks.m11_detector_assisted_beta.run_robust_calibration_gate
"""

from __future__ import annotations

import json
import math
from typing import Any

import numpy as np

from glyphcue.application.beta_stroke_structural import beta_s_signature
from glyphcue.application.occupancy_normalized_distance import (
    occupancy_normalized_distance,
)
from glyphcue.application.sparse_observation_semantics import stable_representative
from glyphcue.application.visual_state_sampling import SampledFrame, group_visual_states
from glyphcue.domain.roi import ROI

from benchmarks.m11_detector_assisted_beta.paddle_text_detector import PaddleTextDetector
from benchmarks.m11_detector_assisted_beta.run_beta_dry_run import _CORPUS_DIR
from benchmarks.m11_detector_assisted_beta.run_occupancy_calibration_gate import (
    _ROI_VARIANTS,
    _calibration_label,
    _observe_window,
    _variant_roi,
)

_CALIBRATION_FIXTURE = "sample_d"


def _fixtures():
    sample_d = _CORPUS_DIR / "sample_d_alpha_window_ground_truth.json"
    generalization = _CORPUS_DIR / "generalization_gate_ground_truth.json"
    if not sample_d.exists() or not generalization.exists():
        return None
    data = json.loads(sample_d.read_text(encoding="utf-8"))
    blob = json.loads(generalization.read_text(encoding="utf-8"))
    fixtures = [
        {
            "name": "sample_d",
            "video": _CORPUS_DIR / data["video_path"],
            "roi": tuple(data["roi"]),
            "window": (data["window_start_seconds"], data["window_end_seconds"]),
            "states": [(s["start_seconds"], s["end_seconds"]) for s in data["states"]],
            "transitions": [tuple(t["window"]) for t in data["transitions"]],
        }
    ]
    for fixture in blob["fixtures"]:
        states = [(s["start_seconds"], s["end_seconds"]) for s in fixture["states"]]
        fixtures.append(
            {
                "name": "sample_a" if "sample_a" in fixture["id"] else "sample_b",
                "video": _CORPUS_DIR / fixture["video_path"],
                "roi": tuple(fixture["roi"]),
                "window": (
                    fixture["window_start_seconds"],
                    fixture["window_end_seconds"],
                ),
                "states": states,
                # This file records blank gaps rather than transition
                # windows; the gaps between consecutive states are the
                # intervals to exclude from calibration labelling.
                "transitions": [
                    (a[1], b[0]) for a, b in zip(states, states[1:])
                ],
            }
        )
    return fixtures, blob["tolerance_seconds"]


def _group(frames, threshold: float):
    return group_visual_states(
        frames,
        group_distance_threshold=threshold,
        distance=occupancy_normalized_distance,
        representative=lambda members: stable_representative(
            members, distance=occupancy_normalized_distance
        ),
    )


def run() -> dict[str, Any] | None:
    loaded = _fixtures()
    if loaded is None:
        print(
            "M11 robust calibration gate skipped: private corpus / "
            "ground-truth files not present on this machine. Safe to run "
            "without them."
        )
        return None
    fixtures, tolerance = loaded
    if not all(fixture["video"].exists() for fixture in fixtures):
        print("M11 robust calibration gate skipped: private corpus absent.")
        return None

    detector = PaddleTextDetector()
    detector.initialize()
    observed: dict[tuple[str, str], list[SampledFrame]] = {}
    try:
        for fixture in fixtures:
            for variant, (shift, scale) in _ROI_VARIANTS.items():
                roi: ROI = _variant_roi(fixture["roi"], shift, scale)
                records = _observe_window(
                    detector, fixture["video"], roi, fixture["window"]
                )
                observed[(fixture["name"], variant)] = [
                    SampledFrame(
                        index=index,
                        timestamp=record["timestamp"],
                        signature=record["signature"],
                        is_blank=record["lines"] == 0,
                    )
                    for index, record in enumerate(records)
                ]
    finally:
        detector.shutdown()

    # ---- phase 1: calibration, sample_d only ---------------------------
    calibration = next(f for f in fixtures if f["name"] == _CALIBRATION_FIXTURE)
    same: list[float] = []
    different: list[float] = []
    for variant in _ROI_VARIANTS:
        frames = observed[(_CALIBRATION_FIXTURE, variant)]
        labels = [
            _calibration_label(
                frame.timestamp, calibration["states"], calibration["transitions"]
            )
            for frame in frames
        ]
        for i in range(len(frames)):
            for j in range(i + 1, len(frames)):
                first, second = labels[i], labels[j]
                if first is None or second is None:
                    continue
                distance = occupancy_normalized_distance(
                    frames[i].signature, frames[j].signature
                )
                if first == second:
                    same.append(distance)
                elif abs(first - second) == 1:
                    different.append(distance)

    s95 = float(np.quantile(same, 0.95))
    d05 = float(np.quantile(different, 0.05))
    print("=== calibration (sample_d and its ROI perturbations only) ===")
    print(f"  {len(same)} same-state pairs, {len(different)} adjacent different-state pairs")
    print(f"  S95 = p95(same-state)      = {s95:.4f}")
    print(f"  D05 = p05(different-state) = {d05:.4f}")
    if d05 <= s95:
        print("  D05 <= S95 -> STOP. No threshold derived, none searched.")
        return {"stopped": True, "threshold": None}
    threshold = round(math.sqrt(s95 * d05), 3)
    print(
        f"  D05 > S95 -> threshold = sqrt(S95*D05) = {math.sqrt(s95 * d05):.4f} "
        f"-> FROZEN at {threshold}"
    )
    print(
        f"  margin: {threshold / s95:.2f}x above S95, {d05 / threshold:.2f}x below D05"
    )

    # ---- phase 2: validation, threshold frozen -------------------------
    print("\n=== validation (metric and threshold frozen) ===")
    print(
        f"{'role':12s}{'fixture':10s}{'variant':18s}{'obs':>5s}{'reps':>6s}"
        f"{'recall':>9s}{'swallowed':>10s}{'maxfrag':>9s}"
    )
    failures = []
    for fixture in fixtures:
        for variant in _ROI_VARIANTS:
            frames = observed[(fixture["name"], variant)]
            representatives = _group(frames, threshold).representative_timestamps
            per_state = [
                sum(
                    1
                    for value in representatives
                    if low - tolerance <= value <= high + tolerance
                )
                for low, high in fixture["states"]
            ]
            covered = sum(1 for count in per_state if count)
            swallowed = len(per_state) - covered
            role = (
                "CALIBRATION" if fixture["name"] == _CALIBRATION_FIXTURE else "HELD-OUT"
            )
            print(
                f"{role:12s}{fixture['name']:10s}{variant:18s}{len(frames):5d}"
                f"{len(representatives):6d}{f'{covered}/{len(per_state)}':>9s}"
                f"{swallowed:10d}{max(per_state):9d}"
            )
            if swallowed and role == "HELD-OUT":
                failures.append((fixture["name"], variant, swallowed))

    print()
    if failures:
        print(f"HELD-OUT FAILURES ({len(failures)}): {failures}")
        print(
            "STOP. The threshold stays as calibration produced it; adjusting "
            "it to fit held-out evidence would destroy the only thing "
            "held-out evidence is for."
        )
    else:
        print("held-out validation clean: no swallowed states anywhere")
    return {"stopped": bool(failures), "threshold": threshold, "failures": failures}


if __name__ == "__main__":
    run()
