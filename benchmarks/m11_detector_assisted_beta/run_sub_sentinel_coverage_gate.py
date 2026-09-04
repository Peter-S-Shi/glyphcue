"""M11 Research Gate -- sub-sentinel coverage / cost gate.

Research-only; production untouched.

THE QUESTION. sample_b's final state lasts about 0.265s, shorter than
the 1.0s detector sentinel, and it is the last correctness gap left
after 350fada: it scores as swallowed on the hand_drawn_tight and
tight_070 ROI variants while every other fixture and variant is clean.
The gate was opened to compare bounded coverage strategies -- a
conditional follow-up, a local boundary guard, a staggered sentinel --
that would give such a state more chances to be observed without
shortening the sentinel globally or pushing detector calls back toward
dense.

THE ANSWER: none of them can help, because coverage is not the failure.

  1. The state IS observed, on time, on every ROI variant. The frozen
     range-boundary rule in `hybrid_evidence_job` -- observe the last
     grid point nothing else claimed -- places an observation squarely
     inside the state's true span on all eight variants. That rule was
     written for exactly this state and it works.

  2. What differs is what the DETECTOR returns there. On the two failing
     variants that observation comes back with zero text lines, so it
     becomes an explicit blank state and contributes no subtitle
     representative -- which is why the state scores as swallowed rather
     than mislabelled.

  3. A dense per-frame sweep of the state's whole span shows this is not
     a timing accident. Under the frozen ROI every frame of the state
     yields two caption lines; under either tight ROI, NO frame of the
     state yields any line at all:

       frozen             274.735-274.968   2 lines on every frame
       hand_drawn_tight   274.735-274.968   0 lines on every frame
       tight_070          274.735-274.968   0 lines on every frame

     There is no frame for a coverage strategy to find. More
     observations, a shorter sentinel, a staggered grid or a higher
     sampling rate would all sample the same undetectable frames, at
     strictly higher detector cost and with no recall to show for it.

WHY THIS CAPTION AND NOT ITS NEIGHBOURS. The detected line widths say
it: the preceding caption measures 32-35% of frame width and survives
the tight crop, while this one measures 81% and 76% across two lines --
a physically larger, taller caption block. An ROI drawn tightly enough
to fit the fixture's typical captions can therefore exclude an
atypically large one completely. That is the same failure class the ROI
Normalization gate (86bd60e) examined and rejected a uniform fix for, so
it is a known consequence of keeping the ROI a coarse, user-drawn
subtitle search envelope, not a new defect.

VERDICT: STOP. The residual risk is real but it belongs to the
detector-and-framing layer, not to the scheduler, and no scheduler
change can retire it. Accepting it, or revisiting the ROI contract, is a
product decision.

Requires the `[ocr]` extra (detection only, no recognition):
    python -m benchmarks.m11_detector_assisted_beta.run_sub_sentinel_coverage_gate
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np

from glyphcue.adapters.pyav_media_source import PyAvMediaFrameSource
from glyphcue.application.detector_assisted_signature import (
    MAX_LINES,
    detected_lines_from_polygons,
)
from glyphcue.application.roi_crop import crop_to_roi
from glyphcue.domain.roi import ROI

from benchmarks.m11_detector_assisted_beta.paddle_text_detector import PaddleTextDetector
from benchmarks.m11_detector_assisted_beta.run_beta_dry_run import _CORPUS_DIR
from benchmarks.m11_detector_assisted_beta.run_occupancy_calibration_gate import (
    _ROI_VARIANTS,
    _variant_roi,
)

_MARGIN_SECONDS = 0.4


def run() -> dict[str, Any] | None:
    path = _CORPUS_DIR / "generalization_gate_ground_truth.json"
    if not path.exists():
        print(
            "M11 sub-sentinel coverage gate skipped: private corpus / "
            "ground-truth files not present on this machine. Safe to run "
            "without them."
        )
        return None
    fixture = next(
        f
        for f in json.loads(path.read_text(encoding="utf-8"))["fixtures"]
        if "sample_b" in f["id"]
    )
    video = _CORPUS_DIR / fixture["video_path"]
    if not video.exists():
        print("M11 sub-sentinel coverage gate skipped: private corpus absent.")
        return None

    shortest = min(
        fixture["states"], key=lambda s: s["end_seconds"] - s["start_seconds"]
    )
    span = (shortest["start_seconds"], shortest["end_seconds"])
    print(
        f"shortest state: {span[0]:.3f}-{span[1]:.3f} "
        f"({span[1] - span[0]:.3f}s, sub-sentinel)"
    )

    detector = PaddleTextDetector()
    detector.initialize()
    detectable: dict[str, int] = {}
    try:
        for variant, (shift, scale) in _ROI_VARIANTS.items():
            roi: ROI = _variant_roi(tuple(fixture["roi"]), shift, scale)
            source = PyAvMediaFrameSource()
            source.open(video)
            frames_in_state = 0
            with_lines = 0
            try:
                for timestamp, frame in source.frames(
                    span[0] - _MARGIN_SECONDS, span[1]
                ):
                    if timestamp < span[0]:
                        continue
                    boxes = detected_lines_from_polygons(
                        [
                            np.asarray(p, dtype=np.float64)
                            for p in (detector(crop_to_roi(frame, roi)) or [])
                        ]
                    )[:MAX_LINES]
                    frames_in_state += 1
                    with_lines += 1 if boxes else 0
            finally:
                source.close()
            detectable[variant] = with_lines
            print(
                f"  {variant:18s} {with_lines:3d}/{frames_in_state:3d} frames of the "
                f"state yield any detected line"
            )
    finally:
        detector.shutdown()

    unreachable = [v for v, count in detectable.items() if count == 0]
    if unreachable:
        print(
            "\nSTOP: on "
            + ", ".join(unreachable)
            + " the state is undetectable on EVERY frame, so no coverage "
            "strategy can recover it -- more observations would sample the "
            "same empty frames at higher detector cost. The gap belongs to "
            "the detector-and-framing layer, not the scheduler."
        )
    else:
        print("\nevery ROI variant has at least one detectable frame in the state")
    return {"detectable_frames": detectable, "unreachable": unreachable}


if __name__ == "__main__":
    run()
