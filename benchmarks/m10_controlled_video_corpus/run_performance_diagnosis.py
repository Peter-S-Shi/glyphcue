"""Milestone 10 performance postmortem: isolate where Path A's real
wall-clock time actually goes, on controlled/synthetic fixtures, BEFORE
any optimization is proposed.

Background: a real run against the repo owner's private representative-
video corpus (see docs/m10_private_corpus_incident.md) crashed after
~40 minutes of wall clock. The crash was caused by a real bug in the
EVALUATION HARNESS (benchmarks/private_video_corpus/run_evaluation.py's
`_run_job` never called `job.request_cancel()` on its own timeout, so
timed-out jobs kept running, orphaned, while the outer loop started
MORE jobs concurrently -- resource contention, not a clean sequential
run). That confounds any attempt to read a single "Path A is Nx slower
than realtime" number directly off that crashed run. This script
measures each real cost in isolation, on small deterministic fixtures,
so later M10/M11 optimization decisions are evidence-based, not a guess
from one confounded total.

Every timing below uses the REAL, frozen production seams (real
PaddleOcrEngine, real build_ocr_evidence_job /
build_multilingual_ocr_evidence_job, real reconstruct_cues_with_consensus
/ reconstruct_multilingual_cues_for_track_group, real
ObservationRepository) -- nothing here is estimated.

Run manually (requires the `[ocr]` extra):
    python -m benchmarks.m10_controlled_video_corpus.run_performance_diagnosis
"""

from __future__ import annotations

import json
import statistics
import time
import uuid
from pathlib import Path

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from glyphcue.adapters.paddleocr_engine import PaddleOcrEngine
from glyphcue.adapters.pyav_media_source import PyAvMediaFrameSource
from glyphcue.application.consensus_reconstruction import reconstruct_cues_with_consensus
from glyphcue.application.multilingual_ocr_evidence_job import build_multilingual_ocr_evidence_job
from glyphcue.application.multilingual_reconstruction import (
    reconstruct_multilingual_cues_for_track_group,
)
from glyphcue.application.ocr_evidence_job import build_ocr_evidence_job
from glyphcue.application.ocr_invocation_policy import NaiveDenseOcrPolicy
from glyphcue.application.pipeline_metrics import PipelineMetrics
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.application.roi_crop import crop_to_roi
from glyphcue.domain.observation import Observation
from glyphcue.domain.provenance import Provenance, ProvenanceKind
from glyphcue.domain.roi import ROI
from glyphcue.domain.track_group import TrackGroup
from glyphcue.persistence.database import connect
from glyphcue.persistence.observation_repository import ObservationRepository

from benchmarks.m10_controlled_video_corpus.fixture import FIXTURES, generate_fixture

FIXTURE_DIR = Path(__file__).parent / "generated_fixture"
RESULTS_PATH = Path(__file__).parent / "performance_diagnosis_results.json"
_FULL_ROI = ROI(x=0.0, y=0.0, width=1.0, height=1.0)
_JOB_TIMEOUT_SECONDS = 60.0


def _run_job_or_cancel(job) -> str:
    """Fixes the bug found in benchmarks/private_video_corpus/run_evaluation.py:
    on timeout, actually requests cancellation AND waits (bounded) for the
    background thread to really stop, instead of abandoning it orphaned.
    Also subscribes to `job.progress` so a run is never silently invisible
    again. Returns the real terminal job state name."""
    progress_log: list[tuple[str, float, float]] = []
    job.progress.connect(lambda phase, done, total: progress_log.append((phase, done, total)))

    loop = QEventLoop()
    job.finished.connect(loop.quit)
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(int(_JOB_TIMEOUT_SECONDS * 1000))
    job.start()
    loop.exec()

    if job.state.value == "running":
        print(f"  [!] job exceeded {_JOB_TIMEOUT_SECONDS}s -- requesting real cancellation, not abandoning it")
        job.request_cancel()
        cancel_loop = QEventLoop()
        job.finished.connect(cancel_loop.quit)
        cancel_timer = QTimer()
        cancel_timer.setSingleShot(True)
        cancel_timer.timeout.connect(cancel_loop.quit)
        cancel_timer.start(10_000)
        cancel_loop.exec()

    job.wait(timeout=5.0)
    if progress_log:
        last_phase, last_done, last_total = progress_log[-1]
        print(f"  progress: {len(progress_log)} updates, last={last_phase} {last_done:.2f}/{last_total:.2f}s")
    return job.state.value


def _time_engine_construction(language: str) -> tuple[float, PaddleOcrEngine]:
    start = time.perf_counter()
    engine = PaddleOcrEngine(language=language)
    engine.initialize()
    return time.perf_counter() - start, engine


def _time_pure_decode(video_path: Path, duration_seconds: float) -> dict:
    source = PyAvMediaFrameSource()
    source.open(video_path)
    start = time.perf_counter()
    frame_count = 0
    for _timestamp, _frame in source.frames(0.0, duration_seconds):
        frame_count += 1
    elapsed = time.perf_counter() - start
    source.close()
    return {
        "frames_decoded": frame_count,
        "elapsed_seconds": round(elapsed, 4),
        "frames_per_second": round(frame_count / elapsed, 2) if elapsed > 0 else 0.0,
    }


def _time_ocr_call_latencies(engine: PaddleOcrEngine, video_path: Path, duration_seconds: float, roi: ROI) -> dict:
    source = PyAvMediaFrameSource()
    source.open(video_path)
    latencies = []
    for _timestamp, frame in source.frames(0.0, duration_seconds):
        roi_frame = crop_to_roi(frame, roi)
        call_start = time.perf_counter()
        engine.recognize(roi_frame)
        latencies.append(time.perf_counter() - call_start)
    source.close()
    if not latencies:
        return {"call_count": 0}
    sorted_latencies = sorted(latencies)
    return {
        "call_count": len(latencies),
        "mean_seconds": round(statistics.mean(latencies), 4),
        "median_seconds": round(statistics.median(latencies), 4),
        "p95_seconds": round(sorted_latencies[int(0.95 * (len(sorted_latencies) - 1))], 4),
        "min_seconds": round(min(latencies), 4),
        "max_seconds": round(max(latencies), 4),
    }


def _time_persistence(db_path: Path, count: int) -> dict:
    conn = connect(db_path)
    repository = ObservationRepository(conn)
    evidence_run_id = str(uuid.uuid4())
    start = time.perf_counter()
    for index in range(count):
        repository.add(
            Observation(
                id=str(uuid.uuid4()),
                text=f"synthetic-{index}",
                start_time=float(index),
                end_time=float(index) + 0.1,
                provenance=Provenance(kind=ProvenanceKind.OCR_ENGINE, source="diagnosis"),
            ),
            evidence_run_id,
        )
    elapsed = time.perf_counter() - start
    conn.close()
    return {
        "observation_count": count,
        "elapsed_seconds": round(elapsed, 4),
        "observations_per_second": round(count / elapsed, 1) if elapsed > 0 else 0.0,
    }


def _run_real_job(video_path: Path, languages: tuple[str, ...], db_path: Path, *, dense: bool) -> tuple[PipelineMetrics, list, str, float]:
    metrics = PipelineMetrics()
    evidence_run_id = str(uuid.uuid4())
    processing_range = ProcessingRange()
    policy = NaiveDenseOcrPolicy() if dense else None
    outer_start = time.perf_counter()

    if len(languages) > 1:
        track_group = TrackGroup(id=f"tg-{evidence_run_id}", roi=_FULL_ROI, languages=languages)
        engines = {language: PaddleOcrEngine(language=language) for language in languages}
        job = build_multilingual_ocr_evidence_job(
            video_path, processing_range, track_group, engines, db_path, metrics, evidence_run_id, policy=policy
        )
    else:
        engine = PaddleOcrEngine(language=languages[0])
        job = build_ocr_evidence_job(
            video_path, processing_range, _FULL_ROI, engine, db_path, metrics, evidence_run_id, policy=policy
        )

    state = _run_job_or_cancel(job)
    outer_elapsed = time.perf_counter() - outer_start

    read_conn = connect(db_path)
    observations = ObservationRepository(read_conn).list_for_run(evidence_run_id)
    read_conn.close()
    if len(languages) > 1:
        cues, _diagnostics = reconstruct_multilingual_cues_for_track_group(observations, track_group)
    else:
        cues, _diagnostics = reconstruct_cues_with_consensus(observations)
    return metrics, cues, state, outer_elapsed


def run() -> dict:
    app = QApplication.instance() or QApplication([])
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    results: dict = {"fixtures": []}

    for fixture in FIXTURES:
        print(f"=== {fixture.id} ===")
        video_path = FIXTURE_DIR / f"{fixture.id}.mp4"
        frames_written = generate_fixture(fixture, video_path)
        duration_seconds = frames_written[-1][0] / 1000.0 + 0.1

        entry: dict = {"id": fixture.id, "media_duration_seconds": round(duration_seconds, 2)}

        construction_time, engine = _time_engine_construction(fixture.languages[0])
        entry["engine_construction_seconds"] = round(construction_time, 4)

        entry["pure_decode"] = _time_pure_decode(video_path, duration_seconds)
        entry["ocr_call_latency"] = _time_ocr_call_latencies(engine, video_path, duration_seconds, _FULL_ROI)
        engine.shutdown()

        db_path = FIXTURE_DIR / f"{fixture.id}_persistence.sqlite3"
        entry["persistence_1000_observations"] = _time_persistence(db_path, 1000)
        db_path.unlink(missing_ok=True)

        for label, dense in (("selective", False), ("dense", True)):
            run_db_path = FIXTURE_DIR / f"{fixture.id}_{label}.sqlite3"
            metrics, cues, state, outer_elapsed = _run_real_job(video_path, fixture.languages, run_db_path, dense=dense)
            run_db_path.unlink(missing_ok=True)
            entry[f"{label}_run"] = {
                "job_final_state": state,
                "frames_analyzed": metrics.frames_analyzed,
                "ocr_calls": metrics.ocr_calls,
                "observations_created": metrics.observations_created,
                "cue_count": len(cues),
                "media_duration_seconds": round(metrics.media_seconds_processed, 3),
                "wall_clock_processing_seconds": round(metrics.elapsed_seconds, 3),
                "processing_time_to_media_duration_ratio": round(
                    metrics.elapsed_seconds / metrics.media_seconds_processed, 3
                )
                if metrics.media_seconds_processed > 0
                else None,
                "outer_script_wall_clock_seconds": round(outer_elapsed, 3),
                "harness_waiting_overhead_seconds": round(outer_elapsed - metrics.elapsed_seconds, 3),
            }

        results["fixtures"].append(entry)

    RESULTS_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Wrote {RESULTS_PATH}")
    return results


if __name__ == "__main__":
    run()
