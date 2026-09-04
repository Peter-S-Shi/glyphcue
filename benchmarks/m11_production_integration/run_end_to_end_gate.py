"""M11 Production Integration & Real OCR End-to-End Gate.

The first run of the M11 research candidate through the REAL Path A job
with REAL PaddleOCR recognition, against the shipped production trigger
path on the same three frozen windows.

Both profiles go through their real job builders, real
`PaddleOcrEngine`, real SQLite persistence and real `ObservationRepository`
reads -- nothing is simulated and no cost is extrapolated. What is
compared:

  * wall clock, recognition calls, detector calls (hybrid only)
  * Observations produced, and the subtitle TEXT each profile recovered
  * semantic transition coverage against the manual ground truth
  * Cue count and Cue start/end timing after real reconstruction

The research prediction under test: sample_d's ~53 recognition
candidates fall to roughly 10, and the ~43.8s per-window estimate holds
once real recognition is paid for.

Requires the `[ocr]` extra and the private corpus:
    python -m benchmarks.m11_production_integration.run_end_to_end_gate
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from glyphcue.application.evidence_job_profile import (
    EvidenceJobProfile,
    build_evidence_job_for_profile,
)
from glyphcue.application.pipeline_metrics import PipelineMetrics
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.application.reconstruction import reconstruct_cues
from glyphcue.domain.roi import ROI
from glyphcue.persistence.database import connect
from glyphcue.persistence.observation_repository import ObservationRepository

from benchmarks.m11_detector_assisted_beta.paddle_text_detector import PaddleTextDetector
from benchmarks.m11_detector_assisted_beta.run_beta_dry_run import (
    _CORPUS_DIR,
    _load_fixtures,
    _tolerance_seconds,
)

_PROFILES = ("production", "hybrid")


def _covered(states: list[dict], timestamps: list[float], tolerance: float) -> list[int]:
    """Which real subtitle states got at least one observation of their
    own -- the semantic transition coverage this whole gate protects."""
    return [
        state["index"]
        for state in states
        if not any(
            state["start_seconds"] - tolerance <= t <= state["end_seconds"] + tolerance
            for t in timestamps
        )
    ]


def _run_profile(profile, fixture, engine, detector, db_path) -> dict[str, Any]:
    run_id = str(uuid.uuid4())
    metrics = PipelineMetrics()
    job = build_evidence_job_for_profile(
        EvidenceJobProfile.PRODUCTION_TRIGGER
        if profile == "production"
        else EvidenceJobProfile.EXPERIMENTAL_HYBRID,
        _CORPUS_DIR / fixture["video_path"],
        ProcessingRange(
            start_time=fixture["window_start_seconds"],
            end_time=fixture["window_end_seconds"],
        ),
        ROI(*fixture["roi"]),
        engine,
        db_path,
        metrics,
        run_id,
        detect=None if profile == "production" else detector,
    )

    wall_start = time.monotonic()
    job.start()
    job.wait(timeout=3600)
    wall = time.monotonic() - wall_start

    conn = connect(db_path)
    try:
        observations = ObservationRepository(conn).list_for_run(run_id)
    finally:
        conn.close()

    cues = reconstruct_cues(observations)
    texts = [o.text for o in observations if o.text]
    return {
        "job_state": str(job.state),
        "wall_seconds": round(wall, 2),
        "recognition_calls": metrics.ocr_calls,
        "detector_calls": metrics.detector_calls,
        "detector_seconds": round(metrics.detector_seconds, 2),
        "frames_analyzed": metrics.frames_analyzed,
        "observations": len(observations),
        "non_empty_observations": len(texts),
        "blank_markers": len(observations) - len(texts),
        "unique_texts": sorted(set(texts)),
        "observation_timestamps": [round(o.start_time, 3) for o in observations],
        "cue_count": len(cues),
        "cues": [
            (
                round(c.start_time, 3),
                round(c.end_time, 3),
                " | ".join(layer.text for layer in c.language_layers),
            )
            for c in cues
        ],
    }


def run() -> dict[str, Any] | None:
    fixtures = _load_fixtures()
    if not fixtures:
        print(
            "M11 end-to-end gate skipped: private corpus / ground-truth files "
            "not present on this machine. Safe to run without them."
        )
        return None

    try:
        from glyphcue.adapters.paddleocr_engine import PaddleOcrEngine
    except ImportError:
        print("M11 end-to-end gate skipped: the `[ocr]` extra is not installed.")
        return None

    tolerance = _tolerance_seconds()
    detector = PaddleTextDetector()
    detector.initialize()

    reports = []
    try:
        for fixture in fixtures:
            video_path = _CORPUS_DIR / fixture["video_path"]
            if not video_path.exists():
                print(f"Skipping {fixture['id']}: {video_path.name} not present.")
                continue
            states = fixture["states"]

            results = {}
            for profile in _PROFILES:
                db_path = _CORPUS_DIR.parent / f"m11_e2e_{fixture['id']}_{profile}.sqlite3"
                if db_path.exists():
                    db_path.unlink()
                results[profile] = _run_profile(
                    profile, fixture, PaddleOcrEngine(), detector, db_path
                )
                results[profile]["missed_states"] = _covered(
                    states, results[profile]["observation_timestamps"], tolerance
                )
                db_path.unlink(missing_ok=True)

            hybrid = results["hybrid"]
            production = results["production"]
            passed = (
                not hybrid["missed_states"]
                and hybrid["recognition_calls"] < production["recognition_calls"]
                and hybrid["wall_seconds"] < production["wall_seconds"]
            )
            reports.append({"fixture_id": fixture["id"], **results, "PASS": passed})

            print(f"\n=== Fixture: {fixture['id']} ===")
            print(f"  Real subtitle states: {len(states)}")
            print(f"  {'':30}{'production':>14}{'hybrid':>14}")
            for label, key in (
                ("wall clock (s)", "wall_seconds"),
                ("recognition calls", "recognition_calls"),
                ("detector calls", "detector_calls"),
                ("detector seconds", "detector_seconds"),
                ("frames analyzed", "frames_analyzed"),
                ("observations", "observations"),
                ("  with text", "non_empty_observations"),
                ("  blank markers", "blank_markers"),
                ("distinct texts", "unique_texts"),
                ("cues reconstructed", "cue_count"),
                ("states with no observation", "missed_states"),
                ("job state", "job_state"),
            ):
                left, right = production[key], hybrid[key]
                if isinstance(left, list):
                    left, right = len(left), len(right)
                print(f"  {label:30}{str(left):>14}{str(right):>14}")

            for profile in _PROFILES:
                print(f"  --- {profile} cues ---")
                for start, end, text in results[profile]["cues"]:
                    print(f"    [{start:7.3f} -> {end:7.3f}]  {text}")
            print(f"  PASS: {passed}")
    finally:
        detector.shutdown()

    overall = bool(reports) and all(r["PASS"] for r in reports)
    print(f"\n=== M11 End-to-End Gate: {'PASS' if overall else 'FAIL'} ===")
    result = {"fixtures": reports, "overall_pass": overall}

    # A run of this gate costs real recognition on real media and takes
    # many minutes; writing the full result out means an analysis
    # question never forces a re-run. GLYPHCUE_E2E_REPORT is honored so
    # the destination can be kept off the repository -- these reports
    # quote private subtitle text and must never be committed.
    destination = os.environ.get("GLYPHCUE_E2E_REPORT")
    if destination:
        Path(destination).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Full report written to {destination}")
    return result


if __name__ == "__main__":
    run()
