"""Private representative-video corpus evaluation (M10 harness, M11 stage 5 corpus).

Runs a real, unmodified Path A pipeline against a PRIVATE, gitignored
representative-video corpus the repo owner supplied locally: real
`PaddleOcrEngine`, real `reconstruct_cues_with_consensus` /
`reconstruct_multilingual_cues_for_track_group`, no algorithm change and
no Review Priority involvement.

Which Path A evidence strategy it uses is named by `EVALUATION_PROFILE`
rather than implied, so a reader of a results file can tell which
pipeline produced it. M11 stage 5-C froze that at
`EvidenceJobProfile.EXPERIMENTAL_HYBRID`; multilingual entries are a
known open question under that profile -- see `preflight()`, which
refuses rather than picking a language on the caller's behalf.

This script is tracked; the corpus manifest and video files it reads are
NOT. If `private_samples/m10_video_corpus/manifest.json` does not exist
(any other machine, CI, a fresh clone), `run()` returns `None` and prints
a message instead of failing -- this script must be safely runnable
without the private assets ever being present.

**Not run for Milestone 10, and not yet run for Milestone 11.** M11
stage 5 froze a five-window corpus and one ROI per window, confirmed the
ground truth for the four new samples, and re-verified the crash
condition below (`--crash-check`); the evaluation itself has not been
started. The one real M10 attempt against this corpus
crashed after ~40 minutes of wall clock, exposing a real bug in this
script's own job orchestration (fixed via the shared, hardened
`benchmarks._job_harness.run_job_or_cancel`, per
`docs/m10_private_corpus_incident.md`) compounded by a real, separately
diagnosed product-performance cost (`docs/m10_performance_diagnosis.md`).
`run_job_or_cancel` never returns while a job's worker thread may still
be alive: if cancellation is requested but the job does not reach a
terminal state within its grace period, it raises
`EvaluationJobDidNotTerminateError` and this script's `for entry in
entries:` loop (no try/except around it) aborts the whole run rather
than starting the next entry.
The controlled/synthetic corpus in `benchmarks/m10_controlled_video_corpus/`
closes only the reproducible performance-diagnosis seam, not ROADMAP
§17's representative-video target -- that target is transferred to
Milestone 11 as a mandatory acceptance gate, not waived (see
`docs/m10_private_corpus_incident.md`, `ROADMAP.md` §17/§18). This script
is kept, fixed, and tracked so Milestone 11 can safely re-attempt the
real corpus once its performance-hardening scope addresses the
underlying cost.

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
    python -m benchmarks.private_video_corpus.run_evaluation --preflight
    python -m benchmarks.private_video_corpus.run_evaluation --crash-check
    python -m benchmarks.private_video_corpus.run_evaluation

`--preflight` validates the corpus, the ROI table and the frozen profile
without running anything; `--crash-check` re-verifies the M10 incident's
orchestration failure against the real windows using a stub recognizer,
so it can never become an accidental evaluation run. `run()` refuses to
start unless `preflight()` passes.
"""

from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path

from PySide6.QtWidgets import QApplication

from benchmarks._job_harness import run_job_or_cancel
from glyphcue.adapters.paddleocr_engine import PaddleOcrEngine
from glyphcue.adapters.paddleocr_text_detector import PaddleOcrTextDetector
from glyphcue.adapters.pyav_media_source import probe_media
from glyphcue.application.consensus_reconstruction import reconstruct_cues_with_consensus
from glyphcue.application.evidence_job_profile import (
    EvidenceJobProfile,
    build_evidence_job_for_profile,
)
from glyphcue.application.multilingual_ocr_evidence_job import build_multilingual_ocr_evidence_job
from glyphcue.application.multilingual_reconstruction import (
    reconstruct_multilingual_cues_for_track_group,
)
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
    # M10's four entries, unchanged.
    "private-a-clean-zh": ROI(x=0.05, y=0.80, width=0.90, height=0.15),
    "private-d-bilingual-typical": ROI(x=0.05, y=0.72, width=0.90, height=0.23),
    "private-b-difficult-styled": ROI(x=0.05, y=0.80, width=0.90, height=0.16),
    "private-c-difficult-mixed-format": ROI(x=0.05, y=0.50, width=0.90, height=0.47),
    # M11 stage 5's frozen corpus. Each of these was measured against its own
    # window and approved at the stage 5-B human gate; see
    # docs/m11_representative_evaluation.md section 6 for what each one
    # covers and, where a distractor could not be excluded by a rectangle,
    # why the trade-off went the way it did.
    "private-g-english-handheld": ROI(x=0.05, y=0.80, width=0.90, height=0.20),
    "private-e-chinese-screenshare": ROI(x=0.05, y=0.85, width=0.90, height=0.15),
    "private-h-bilingual-fixed-overlay": ROI(x=0.05, y=0.73, width=0.90, height=0.19),
    "private-f-bilingual-fast-broll": ROI(x=0.05, y=0.76, width=0.90, height=0.24),
}

# Stage 5-C's evaluation profile, frozen at the stage 5-B human gate.
# Named here rather than defaulted so a reader of a results file can tell
# which pipeline produced it (the same reason
# `evidence_job_profile.build_evidence_job_for_profile` makes callers name
# their profile).
EVALUATION_PROFILE = EvidenceJobProfile.EXPERIMENTAL_HYBRID


def _run_single_language_job(video_path: Path, entry: CorpusEntry, db_path: Path) -> tuple[PipelineMetrics, list, str]:
    engine = PaddleOcrEngine(language=entry.languages[0])
    metrics = PipelineMetrics()
    evidence_run_id = str(uuid.uuid4())
    processing_range = ProcessingRange(entry.segment_start_seconds, entry.segment_end_seconds)
    detector = None
    if EVALUATION_PROFILE is EvidenceJobProfile.EXPERIMENTAL_HYBRID:
        detector = PaddleOcrTextDetector()
        detector.initialize()
    try:
        job = build_evidence_job_for_profile(
            EVALUATION_PROFILE,
            video_path,
            processing_range,
            _ROI_BY_ENTRY_ID[entry.id],
            engine,
            db_path,
            metrics,
            evidence_run_id,
            detect=detector,
        )
        state = run_job_or_cancel(job, timeout_seconds=_JOB_TIMEOUT_SECONDS)
    finally:
        # The detector holds a real model; release it before the next entry
        # constructs its own, rather than leaving one per entry alive for
        # the length of the run.
        if detector is not None:
            detector.shutdown()
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
    state = run_job_or_cancel(job, timeout_seconds=_JOB_TIMEOUT_SECONDS)
    read_conn = connect(db_path)
    observations = ObservationRepository(read_conn).list_for_run(evidence_run_id)
    read_conn.close()
    cues, _diagnostics = reconstruct_multilingual_cues_for_track_group(observations, track_group)
    return metrics, cues, state


_JOB_TIMEOUT_SECONDS = 600.0


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


class PreflightError(RuntimeError):
    """The corpus, ROI table and frozen profile do not agree well enough
    for a run to start. Raised before any job is constructed: the M10
    incident (docs/m10_private_corpus_incident.md) is a standing reminder
    that a run which discovers its problems entry-by-entry, mid-flight,
    is the expensive way to find them."""


def preflight() -> dict:
    """Check everything a real run depends on, without running one.

    Returns a report; raises `PreflightError` listing every problem at
    once rather than the first one found."""
    if not MANIFEST_PATH.exists():
        raise PreflightError(f"no corpus manifest at {MANIFEST_PATH}")

    entries = load_corpus_manifest(MANIFEST_PATH)
    problems: list[str] = []
    rows = []

    for entry in entries:
        video_path = MANIFEST_PATH.parent / entry.video_path
        if not video_path.exists():
            problems.append(f"{entry.id}: video {entry.video_path} not found")
        roi = _ROI_BY_ENTRY_ID.get(entry.id)
        if roi is None:
            problems.append(f"{entry.id}: no ROI in _ROI_BY_ENTRY_ID")

        duration = None
        if video_path.exists():
            duration = probe_media(video_path).duration_seconds
            try:
                ProcessingRange(
                    entry.segment_start_seconds, entry.segment_end_seconds
                ).resolve(duration)
            except ValueError as error:
                problems.append(f"{entry.id}: processing range rejected -- {error}")

        multilingual = len(entry.languages) > 1
        if multilingual and EVALUATION_PROFILE is EvidenceJobProfile.EXPERIMENTAL_HYBRID:
            problems.append(
                f"{entry.id}: {EVALUATION_PROFILE.value} is single-language by construction "
                f"(build_hybrid_ocr_evidence_job takes one engine) but this entry declares "
                f"{list(entry.languages)}; refusing to pick a language on the caller's behalf"
            )

        instants = {round((cue.start_time + cue.end_time) / 2, 3) for cue in entry.ground_truth_cues}
        outside = [
            instant for instant in instants
            if not entry.segment_start_seconds <= instant <= entry.segment_end_seconds
        ]
        if outside:
            problems.append(f"{entry.id}: {len(outside)} ground-truth instants fall outside the window")

        rows.append({
            "entry_id": entry.id,
            "languages": list(entry.languages),
            "window": [entry.segment_start_seconds, entry.segment_end_seconds],
            "media_duration_seconds": round(duration, 2) if duration is not None else None,
            "roi": [roi.x, roi.y, roi.width, roi.height] if roi else None,
            "ground_truth_cues": len(entry.ground_truth_cues),
            "verified_instants": len(instants),
            "runnable_under_frozen_profile": not (
                multilingual and EVALUATION_PROFILE is EvidenceJobProfile.EXPERIMENTAL_HYBRID
            ),
        })

    report = {"profile": EVALUATION_PROFILE.value, "manifest": str(MANIFEST_PATH), "entries": rows}
    if problems:
        bullets = "".join(f"{chr(10)}  - {problem}" for problem in problems)
        raise PreflightError("preflight failed; nothing was run:" + bullets)
    return report


class _StubOcrEngine:
    """Stands in for the real runtime during the crash-condition check.

    The M10 incident was an orchestration bug, not an OCR bug: an
    overrunning job was abandoned rather than cancelled, so the next
    entry's job started while the previous worker thread was still alive.
    Re-verifying that on the real windows only needs the real decode,
    range-resolution and job/cancellation machinery -- recognition itself
    is the expensive part and is deliberately stubbed out, so this check
    can never turn into an accidental evaluation run.
    """

    def initialize(self) -> None:
        return None

    def recognize(self, image: object) -> list:
        return []

    def supported_languages(self) -> tuple[str, ...]:
        return ("en", "zh")

    def runtime_info(self):
        from glyphcue.adapters.ocr_types import OcrRuntimeInfo

        return OcrRuntimeInfo(
            engine_name="crash-condition-check-stub", version="0", backend="none"
        )

    def shutdown(self) -> None:
        return None


def crash_condition_check(*, timeout_seconds: float = 1.0) -> dict:
    """Re-verify the M10 crash condition against the frozen windows.

    For every entry: build the real evidence job on the real window, let
    it overrun a deliberately tiny timeout, and confirm the hardened
    harness actually cancels it to a terminal state instead of leaving an
    orphaned worker thread behind. Also confirms the second, smaller M10
    bug is gone -- the temporary directory the run writes its databases
    into must delete cleanly, which it could not while a SQLite
    connection was left open.
    """
    if not MANIFEST_PATH.exists():
        return {"skipped": "no private corpus manifest"}

    QApplication.instance() or QApplication([])
    entries = load_corpus_manifest(MANIFEST_PATH)
    rows = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for entry in entries:
            video_path = MANIFEST_PATH.parent / entry.video_path
            db_path = Path(tmpdir) / f"crashcheck-{entry.id}.sqlite3"
            metrics = PipelineMetrics()
            # Check each entry through the job type it would really use:
            # the frozen profile where it supports the entry, the
            # production job where it does not. Both have their own work
            # loop, so verifying only one would leave the other's
            # cancellation path unexercised on these windows.
            hybrid = (
                EVALUATION_PROFILE is EvidenceJobProfile.EXPERIMENTAL_HYBRID
                and len(entry.languages) == 1
            )
            job = build_evidence_job_for_profile(
                EVALUATION_PROFILE if hybrid else EvidenceJobProfile.PRODUCTION_TRIGGER,
                video_path,
                ProcessingRange(entry.segment_start_seconds, entry.segment_end_seconds),
                _ROI_BY_ENTRY_ID[entry.id],
                _StubOcrEngine(),
                db_path,
                metrics,
                str(uuid.uuid4()),
                detect=(lambda roi_frame: []) if hybrid else None,
            )
            state = run_job_or_cancel(job, timeout_seconds=timeout_seconds, cancel_grace_seconds=30.0)
            rows.append({
                "entry_id": entry.id,
                "job_profile": (EVALUATION_PROFILE if hybrid else EvidenceJobProfile.PRODUCTION_TRIGGER).value,
                "terminal_state": state,
                "worker_thread_still_alive": job.state.value == "running",
                "media_seconds_processed": round(metrics.media_seconds_processed, 3),
            })
    # Reaching here means the TemporaryDirectory context exited without
    # raising: on Windows that is exactly the M10 secondary bug's symptom
    # (a still-open SQLite connection turned cleanup into PermissionError),
    # so surviving the exit IS the check.
    return {
        "timeout_seconds": timeout_seconds,
        "entries": rows,
        "every_job_reached_a_terminal_state": all(
            row["terminal_state"] in {"succeeded", "failed", "cancelled"} for row in rows
        ),
        # A job that raised also "reaches a terminal state", so the
        # M10 orphaned-thread question is only answered by every job
        # ending in `cancelled` -- overran, was asked to stop, and did.
        # Anything `failed` here means the check itself is broken and its
        # verdict must not be read as evidence.
        "every_job_cancelled_cleanly": all(row["terminal_state"] == "cancelled" for row in rows),
        "entries_that_failed": [
            row["entry_id"] for row in rows if row["terminal_state"] == "failed"
        ],
        "any_worker_thread_left_alive": any(row["worker_thread_still_alive"] for row in rows),
        "temporary_directory_deleted_cleanly": True,
    }


def run() -> dict | None:
    if not MANIFEST_PATH.exists():
        print(f"No private corpus manifest at {MANIFEST_PATH} -- skipping (this is expected on any machine "
              "without the repo owner's local private_samples/).")
        return None

    app = QApplication.instance() or QApplication([])
    preflight()
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
    import sys

    if "--preflight" in sys.argv:
        print(json.dumps(preflight(), ensure_ascii=False, indent=2))
    elif "--crash-check" in sys.argv:
        print(json.dumps(crash_condition_check(), ensure_ascii=False, indent=2))
    else:
        run_results = run()
        if run_results is not None:
            print(json.dumps(run_results, ensure_ascii=False, indent=2))
