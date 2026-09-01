"""M11 Research Gate -- Beta-S stroke-structural comparison.

Runs THREE glyph-evidence rules over the same three frozen real 10s
windows and reports them side by side:

    Beta   (41e80f9)  per-patch dynamic-range midpoint
    Beta-P (fcd1df2)  local-contrast threshold
    Beta-S (this)     paired stroke boundaries -- structure, not
                      foreground/background classification

Everything except that one layer is frozen: same detector configuration,
same 5 fps sampling, same canonical band layout, same cell-mismatch
distance, same 0.10 grouping threshold, same blank rule, same
sampling -> grouping -> representative harness. All three variants also
share byte-identical detector output (the detector runs once per fixture
and its polygons are replayed to the other two), so every difference
observed is attributable to the evidence layer alone.

`within_state_excess` -- representatives collected by a real state
beyond the one it needs -- is the number this round is actually about,
since Beta and Beta-P both already had full recall and differed only in
how badly they split held captions, and in which nuisance did the
splitting.

Requires the `[ocr]` extra (detection only, no recognition):
    python -m benchmarks.m11_detector_assisted_beta.run_beta_s_comparison
"""

from __future__ import annotations

from typing import Any

from glyphcue.application.beta_detector_dry_run import run_beta_detector_dry_run
from glyphcue.application.beta_photometric_ink import beta_p_signature
from glyphcue.application.beta_stroke_structural import beta_s_signature
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.domain.roi import ROI

from benchmarks.m11_detector_assisted_beta.paddle_text_detector import PaddleTextDetector
from benchmarks.m11_detector_assisted_beta.run_beta_dry_run import (
    _CORPUS_DIR,
    _FROZEN_SAMPLING_FPS,
    _HARD_MAX_REPRESENTATIVES,
    _load_fixtures,
    _tolerance_seconds,
)
from benchmarks.m11_detector_assisted_beta.run_beta_p_comparison import _summarize
from benchmarks.m11_detector_assisted_beta.run_beta_n_comparison import _RecordingDetector


def run() -> dict[str, Any] | None:
    fixtures = _load_fixtures()
    if not fixtures:
        print(
            "M11 Beta-S comparison skipped: private corpus / ground-truth "
            "files not present on this machine. Safe to run without them."
        )
        return None

    tolerance = _tolerance_seconds()
    detector = PaddleTextDetector()
    detector.initialize()
    recorder = _RecordingDetector(detector)

    reports = []
    try:
        for fixture in fixtures:
            video_path = _CORPUS_DIR / fixture["video_path"]
            if not video_path.exists():
                print(f"Skipping {fixture['id']}: {video_path.name} not present.")
                continue

            roi = ROI(*fixture["roi"])
            processing_range = ProcessingRange(
                start_time=fixture["window_start_seconds"],
                end_time=fixture["window_end_seconds"],
            )
            states = fixture["states"]

            def _run(signature_fn=None):
                kwargs = {} if signature_fn is None else {"signature_fn": signature_fn}
                return run_beta_detector_dry_run(
                    video_path,
                    processing_range,
                    roi,
                    _FROZEN_SAMPLING_FPS,
                    detect=recorder,
                    **kwargs,
                )

            recorder.record()
            variants = {"beta": _summarize(_run(), states, tolerance)}
            for name, signature_fn in (
                ("beta_p", beta_p_signature),
                ("beta_s", beta_s_signature),
            ):
                recorder.replay()
                variants[name] = _summarize(_run(signature_fn), states, tolerance)

            final = variants["beta_s"]
            passed = (
                final["recall_complete"]
                and not final["swallowed_states"]
                and final["within_hard_cap"]
            )
            reports.append(
                {"fixture_id": fixture["id"], "real_state_count": len(states), **variants, "PASS": passed}
            )

            print(f"\n=== Fixture: {fixture['id']} ===")
            print(f"  Real states / transitions: {len(states)} / {len(states) - 1}")
            print(f"  {'':26}{'Beta':>10}{'Beta-P':>10}{'Beta-S':>10}")
            for label, key in (
                ("representatives", "representative_count"),
                ("transition recall", "recall"),
                ("fragmentation ratio", "fragmentation_ratio"),
                ("within-state excess reps", "within_state_excess"),
                ("blank groups", "blank_group_count"),
            ):
                row = "".join(f"{str(variants[v][key]):>10}" for v in ("beta", "beta_p", "beta_s"))
                print(f"  {label:26}{row}")
            row = "".join(
                f"{str(variants[v]['swallowed_states'] or 'none'):>10}"
                for v in ("beta", "beta_p", "beta_s")
            )
            print(f"  {'swallowed states':26}{row}")
            print("  representatives per real state (Beta -> Beta-P -> Beta-S):")
            for state in states:
                index = state["index"]
                marker = "   <-- LOST" if variants["beta_s"]["per_state"][index] == 0 else ""
                counts = " -> ".join(
                    f"{variants[v]['per_state'][index]:>2}" for v in ("beta", "beta_p", "beta_s")
                )
                print(f"    state {index}: {counts}{marker}")
            print(f"  hard cap {_HARD_MAX_REPRESENTATIVES}; PASS: {passed}")
    finally:
        detector.shutdown()

    overall = bool(reports) and all(r["PASS"] for r in reports)
    print(f"\n=== Beta-S Gate: {'PASS' if overall else 'FAIL'} ===")
    return {"fixtures": reports, "overall_pass": overall}


if __name__ == "__main__":
    run()
