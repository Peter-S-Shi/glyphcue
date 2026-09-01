"""Milestone 10 private representative-video corpus evaluation.

Runs the real, frozen production Path A pipeline (`build_ocr_evidence_job`
/ `build_multilingual_ocr_evidence_job`, real `PaddleOcrEngine`, real
`reconstruct_cues_with_consensus` / `reconstruct_multilingual_cues_for_track_group`
-- no algorithm change, no Review Priority involvement) against a PRIVATE,
gitignored representative-video corpus the repo owner supplied locally.

This script is tracked; the corpus manifest and video files it reads are
NOT. If `private_samples/m10_video_corpus/manifest.json` does not exist
(any other machine, CI, a fresh clone), `run()` returns `None` and prints
a message instead of failing -- this script must be safely runnable
without the private assets ever being present.

**Not run for Milestone 10.** The one real attempt against this corpus
crashed after ~40 minutes of wall clock, exposing a real bug in this
script's own job orchestration (fixed below, per
`docs/m10_private_corpus_incident.md`) compounded by a real, separately
diagnosed product-performance cost (`docs/m10_performance_diagnosis.md`).
M10's representative-video evaluation closes on the controlled/synthetic
corpus in `benchmarks/m10_controlled_video_corpus/` instead. This script
is kept, fixed, and tracked so a future milestone can safely re-attempt
the real corpus once the performance question is addressed.

Ground-truth methodology (see the manifest's own per-entry `notes`, kept
private): each entry's ground truth is a small number of
POINT-SAMPLES -- specific verified instants where the real on-screen
caption text was read directly from extracted video frames, independent
of any GlyphCue OCR/reconstruction output. This supports:

- CER per verified point (real text accuracy where GlyphCue produced a
  Cue covering that instant);
- point-recall (fraction of verified instants some real Cue covers at
  all -- did the pipeline not silently drop this moment);
- multilingual layer-assignment correctness at verified bilingual
  instants.

It does NOT support Cue-level precision (a sparse point sample cannot
vouch for every real Cue GlyphCue produces, so an unmatched real Cue is
not evidence of a spurious detection) or timing start/end error (a
+/-1s point window is not a claimed real cue span) -- both are already
covered elsewhere in M10 by the Path B fixture corpus and the synthetic
OCR consensus benchmark. This is a deliberate, stated scope limitation,
not an oversight.

Run manually (requires the `[ocr]` extra AND the private corpus):
    python -m benchmarks.private_video_corpus.run_evaluation
"""

from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from glyphcue.adapters.paddleocr_engine import PaddleOcrEngine
from glyphcue.application.consensus_reconstruction import reconstruct_cues_with_consensus
from glyphcue.application.multilingual_ocr_evidence_job import build_multilingual_ocr_evidence_job
from glyphcue.application.multilingual_reconstruction import (
    reconstruct_multilingual_cues_for_track_group,
)
from glyphcue.application.ocr_evidence_job import build_ocr_evidence_job
from glyphcue.application.pipeline_metrics import PipelineMetrics
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.domain.roi import ROI
from glyphcue.domain.track_group import TrackGroup
from glyphcue.evaluation.corpus import CorpusEntry, load_corpus_manifest
from glyphcue.evaluation.metrics import character_error_rate, multilingual_layer_assignment_errors
from glyphcue.persistence.database import connect
from glyphcue.persistence.observation_repository import ObservationRepository

REPO_ROOT = Path(__file__).parent.parent.parent
MANIFEST_PATH = REPO_ROOT / "private_samples" / "m10_video_corpus" / "manifest.json"
PRIVATE_RESULTS_PATH = MANIFEST_PATH.parent / "evaluation_results.json"

# Not part of the tracked corpus schema (glyphcue.evaluation.corpus has no
# ROI field) -- kept here, keyed by entry id, so the schema stays generic
# and this evaluation-specific detail doesn't leak into it.
_ROI_BY_ENTRY_ID = {
    "private-a-clean-zh": ROI(x=0.05, y=0.80, width=0.90, height=0.15),
    "private-d-bilingual-typical": ROI(x=0.05, y=0.72, width=0.90, height=0.23),
    "private-b-difficult-styled": ROI(x=0.05, y=0.80, width=0.90, height=0.16),
    "private-c-difficult-mixed-format": ROI(x=0.05, y=0.50, width=0.90, height=0.47),
}


def _run_single_language_job(video_path: Path, entry: CorpusEntry, db_path: Path) -> tuple[PipelineMetrics, list, str]:
    engine = PaddleOcrEngine(language=entry.languages[0])
    metrics = PipelineMetrics()
    evidence_run_id = str(uuid.uuid4())
    processing_range = ProcessingRange(entry.segment_start_seconds, entry.segment_end_seconds)
    job = build_ocr_evidence_job(
        video_path, processing_range, _ROI_BY_ENTRY_ID[entry.id], engine, db_path, metrics, evidence_run_id
    )
    state = _run_job_or_cancel(job)
    read_conn = connect(db_path)
    observations = ObservationRepository(read_conn).list_for_run(evidence_run_id)
    read_conn.close()
    cues, _diagnostics = reconstruct_cues_with_consensus(observations)
    return metrics, cues, state


def _run_multilingual_job(video_path: Path, entry: CorpusEntry, db_path: Path) -> tuple[PipelineMetrics, list, str]:
    track_group = TrackGroup(id=f"tg-{entry.id}", roi=_ROI_BY_ENTRY_ID[entry.id], languages=entry.languages)
    engines = {language: PaddleOcrEngine(language=language) for language in entry.languages}
    metrics = PipelineMetrics()
    evidence_run_id = str(uuid.uuid4())
    processing_range = ProcessingRange(entry.segment_start_seconds, entry.segment_end_seconds)
    job = build_multilingual_ocr_evidence_job(
        video_path, processing_range, track_group, engines, db_path, metrics, evidence_run_id
    )
    state = _run_job_or_cancel(job)
    read_conn = connect(db_path)
    observations = ObservationRepository(read_conn).list_for_run(evidence_run_id)
    read_conn.close()
    cues, _diagnostics = reconstruct_multilingual_cues_for_track_group(observations, track_group)
    return metrics, cues, state


_JOB_TIMEOUT_SECONDS = 600.0


def _run_job_or_cancel(job) -> str:
    """M10 incident fix (docs/m10_private_corpus_incident.md): the
    original version of this function quit only the LOCAL Qt event loop
    on timeout, never the job itself -- the job's background thread kept
    running, orphaned, while the caller moved on to start the NEXT
    entry's job, turning an intended sequential run into unbounded
    concurrent execution. This version actually requests cancellation
    and waits (bounded) for the real thread to stop before returning, and
    subscribes to `job.progress` so a long run is never silently
    invisible again."""
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
        cancel_timer.start(30_000)
        cancel_loop.exec()

    job.wait(timeout=5.0)
    if progress_log:
        last_phase, last_done, last_total = progress_log[-1]
        print(f"  progress: {len(progress_log)} updates, last={last_phase} {last_done:.2f}/{last_total:.2f}s")
    return job.state.value


def _cue_covering(cues: list, timestamp: float):
    for cue in cues:
        if cue.start_time <= timestamp <= cue.end_time:
            return cue
    return None


def _evaluate_entry(entry: CorpusEntry, metrics: PipelineMetrics, cues: list, job_state: str) -> dict:
    # Group the manifest's point-sample ground-truth cues (one per
    # language per verified instant) back into one record per instant,
    # by their shared window midpoint.
    points: dict[float, dict[str, str]] = {}
    for gt_cue in entry.ground_truth_cues:
        midpoint = round((gt_cue.start_time + gt_cue.end_time) / 2, 3)
        points.setdefault(midpoint, {})[gt_cue.language or "und"] = gt_cue.text

    matched = 0
    cer_by_language: dict[str, list[float]] = {}
    missing_total = 0
    wrong_assignment_total = 0

    for timestamp, ground_truth_by_language in points.items():
        cue = _cue_covering(cues, timestamp)
        if cue is None:
            continue
        matched += 1
        recovered_by_language = {layer.language: layer.text for layer in cue.language_layers}

        if len(entry.languages) > 1:
            errors = multilingual_layer_assignment_errors(ground_truth_by_language, recovered_by_language)
            missing_total += len(errors["missing"])
            wrong_assignment_total += len(errors["wrong_assignment"])

        for language, truth_text in ground_truth_by_language.items():
            recovered_text = recovered_by_language.get(language, "")
            cer_by_language.setdefault(language, []).append(character_error_rate(truth_text, recovered_text))

    return {
        "entry_id": entry.id,
        "languages": list(entry.languages),
        "job_final_state": job_state,
        "verified_point_count": len(points),
        "point_recall": matched / len(points) if points else 0.0,
        "mean_cer_by_language": {
            language: sum(values) / len(values) for language, values in cer_by_language.items()
        },
        "multilingual_missing_layer_count": missing_total,
        "multilingual_wrong_assignment_count": wrong_assignment_total,
        "performance": {
            # Raw durations kept alongside the derived rates below -- a
            # rate/ratio alone would let a reader lose track of how much
            # real media and real wall-clock time actually produced it.
            "media_duration_seconds": round(metrics.media_seconds_processed, 2),
            "wall_clock_processing_seconds": round(metrics.elapsed_seconds, 2),
            "processing_time_to_media_duration_ratio": round(
                metrics.elapsed_seconds / metrics.media_seconds_processed, 3
            )
            if metrics.media_seconds_processed > 0
            else 0.0,
            "frames_analyzed": metrics.frames_analyzed,
            "ocr_calls": metrics.ocr_calls,
            "frames_analyzed_per_second": round(metrics.frames_analyzed / metrics.elapsed_seconds, 3)
            if metrics.elapsed_seconds > 0
            else 0.0,
            "ocr_calls_per_minute": round(metrics.ocr_calls_per_minute, 2),
            "effective_processing_speed": round(metrics.effective_processing_speed, 4),
        },
    }


def run() -> dict | None:
    if not MANIFEST_PATH.exists():
        print(f"No private corpus manifest at {MANIFEST_PATH} -- skipping (this is expected on any machine "
              "without the repo owner's local private_samples/).")
        return None

    app = QApplication.instance() or QApplication([])
    entries = load_corpus_manifest(MANIFEST_PATH)

    results = {"entries": []}
    with tempfile.TemporaryDirectory() as tmpdir:
        for entry in entries:
            video_path = MANIFEST_PATH.parent / entry.video_path
            db_path = Path(tmpdir) / f"{entry.id}.sqlite3"
            if len(entry.languages) > 1:
                metrics, cues, state = _run_multilingual_job(video_path, entry, db_path)
            else:
                metrics, cues, state = _run_single_language_job(video_path, entry, db_path)
            results["entries"].append(_evaluate_entry(entry, metrics, cues, state))

    PRIVATE_RESULTS_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {PRIVATE_RESULTS_PATH} (private, gitignored)")
    return results


if __name__ == "__main__":
    run_results = run()
    if run_results is not None:
        print(json.dumps(run_results, ensure_ascii=False, indent=2))
