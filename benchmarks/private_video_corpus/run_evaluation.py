"""Private representative-video corpus evaluation (M10 harness, M11 stage 5 corpus).

Runs a real, unmodified Path A pipeline against a PRIVATE, gitignored
representative-video corpus the repo owner supplied locally: real
`PaddleOcrEngine`, real `reconstruct_cues_with_consensus` /
`reconstruct_multilingual_cues_for_track_group`, no algorithm change and
no Review Priority involvement.

Which Path A evidence strategy each entry uses is a per-entry, explicit
choice in `_PROFILE_BY_ENTRY_ID` -- never implied or defaulted -- so a
reader of a results file can always tell which pipeline produced which
entry. M11 stage 5-C's human gate approved a SPLIT profile
(docs/m11_representative_evaluation.md section 13, Option A):
`EvidenceJobProfile.EXPERIMENTAL_HYBRID` for the two single-language
windows (`sample_g`, `sample_e`) and `EvidenceJobProfile.PRODUCTION_TRIGGER`
for the three bilingual ones (`sample_h`, `sample_f`, `sample_c`), since
Hybrid is single-language by construction. `preflight()` requires every
manifest entry to have an assigned profile and refuses a multilingual
entry assigned Hybrid rather than picking a language on the caller's
behalf. Results are grouped strictly by profile
(`_summarize_by_profile`) -- nothing here ever averages a Hybrid entry
and a Production entry into one number.

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
# M10's own manifest -- read-only here, never written. Exists only so the
# completion supplement (run_completion_supplement) can reuse sample_a's
# already-defined M10 window/ROI/ground truth verbatim, without a copy of
# that data drifting into the stage 5 manifest above.
M10_EXPORT_MANIFEST_PATH = MANIFEST_PATH.parent / "export docu" / "manifest.json"

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

# Stage 5-C's split-profile evaluation, approved at the stage 5-C human
# gate (Option A of docs/m11_representative_evaluation.md section 13):
# EXPERIMENTAL_HYBRID cannot run a multilingual entry at all (it is
# single-language by construction -- build_hybrid_ocr_evidence_job takes
# one engine, not a per-language mapping), so the two single-language M11
# stage 5 windows run under it and the three bilingual ones run under the
# shipped PRODUCTION_TRIGGER path instead. This is a real difference in
# which pipeline produced each entry's evidence, not an implementation
# detail -- every consumer of a result (preflight, the crash check, the
# real run, and the report) must be able to say which profile ran which
# entry, and nothing here may quietly average the two together.
#
# M10's four original entries are included for completeness of this
# table (so a caller asking `_PROFILE_BY_ENTRY_ID[entry.id]` for any
# entry this script has ever known about gets an answer) at
# PRODUCTION_TRIGGER, which is what they actually ran under in M10 --
# EXPERIMENTAL_HYBRID did not exist yet.
_PROFILE_BY_ENTRY_ID: dict[str, EvidenceJobProfile] = {
    "private-a-clean-zh": EvidenceJobProfile.PRODUCTION_TRIGGER,
    "private-d-bilingual-typical": EvidenceJobProfile.PRODUCTION_TRIGGER,
    "private-b-difficult-styled": EvidenceJobProfile.PRODUCTION_TRIGGER,
    "private-c-difficult-mixed-format": EvidenceJobProfile.PRODUCTION_TRIGGER,
    "private-g-english-handheld": EvidenceJobProfile.EXPERIMENTAL_HYBRID,
    "private-e-chinese-screenshare": EvidenceJobProfile.EXPERIMENTAL_HYBRID,
    "private-h-bilingual-fixed-overlay": EvidenceJobProfile.PRODUCTION_TRIGGER,
    "private-f-bilingual-fast-broll": EvidenceJobProfile.PRODUCTION_TRIGGER,
}


def _profile_for(entry: CorpusEntry) -> EvidenceJobProfile:
    """The one place that resolves which profile an entry runs under.
    Raises rather than defaulting: an entry this table has no opinion
    about must never silently pick a profile."""
    try:
        return _PROFILE_BY_ENTRY_ID[entry.id]
    except KeyError as error:
        raise PreflightError(f"{entry.id}: no profile assigned in _PROFILE_BY_ENTRY_ID") from error


_JOB_TIMEOUT_SECONDS = 600.0


def _run_single_language_job(
    video_path: Path,
    entry: CorpusEntry,
    db_path: Path,
    *,
    profile: EvidenceJobProfile | None = None,
    timeout_seconds: float = _JOB_TIMEOUT_SECONDS,
) -> tuple[PipelineMetrics, list, str, EvidenceJobProfile]:
    """`profile` defaults to the entry's `_PROFILE_BY_ENTRY_ID` assignment;
    an explicit override exists only for the completion supplement
    (`run_completion_supplement`), which deliberately runs a fixed set of
    entries under Hybrid regardless of what the main split-profile table
    says for them. `timeout_seconds` likewise only differs from the main
    run's default there."""
    profile = profile if profile is not None else _profile_for(entry)
    engine = PaddleOcrEngine(language=entry.languages[0])
    metrics = PipelineMetrics()
    evidence_run_id = str(uuid.uuid4())
    processing_range = ProcessingRange(entry.segment_start_seconds, entry.segment_end_seconds)
    detector = None
    if profile is EvidenceJobProfile.EXPERIMENTAL_HYBRID:
        detector = PaddleOcrTextDetector()
        detector.initialize()
    try:
        job = build_evidence_job_for_profile(
            profile,
            video_path,
            processing_range,
            _ROI_BY_ENTRY_ID[entry.id],
            engine,
            db_path,
            metrics,
            evidence_run_id,
            detect=detector,
        )
        state = run_job_or_cancel(job, timeout_seconds=timeout_seconds)
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
    return metrics, cues, state, profile


def _run_multilingual_job(
    video_path: Path, entry: CorpusEntry, db_path: Path
) -> tuple[PipelineMetrics, list, str, EvidenceJobProfile]:
    profile = _profile_for(entry)
    if profile is not EvidenceJobProfile.PRODUCTION_TRIGGER:
        # Defense in depth: preflight already refuses a multilingual entry
        # assigned EXPERIMENTAL_HYBRID before any job is built, so reaching
        # here with a non-production profile means preflight was bypassed
        # (e.g. a direct call to run()) -- fail loudly rather than build a
        # job under a profile this function does not actually implement.
        raise PreflightError(
            f"{entry.id}: multilingual entry assigned {profile.value}, but only "
            f"{EvidenceJobProfile.PRODUCTION_TRIGGER.value} supports multilingual evidence"
        )
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
    return metrics, cues, state, profile


def _cue_covering(cues: list, timestamp: float):
    for cue in cues:
        if cue.start_time <= timestamp <= cue.end_time:
            return cue
    return None


def _evaluate_entry(
    entry: CorpusEntry,
    metrics: PipelineMetrics,
    cues: list,
    job_state: str,
    profile: EvidenceJobProfile,
) -> dict:
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

    range_seconds = entry.segment_end_seconds - entry.segment_start_seconds
    coverage_ratio = (
        metrics.media_seconds_processed / range_seconds if range_seconds > 0 else 0.0
    )
    # A completion label a reader can act on without cross-referencing
    # job_final_state against coverage by hand: `cancelled` alone does not
    # say whether that meant "barely started" or "essentially finished".
    if job_state == "succeeded":
        completion = "completed"
    elif job_state == "cancelled" and coverage_ratio >= 0.98:
        completion = "completed_via_timeout_cancel"
    elif job_state == "cancelled":
        completion = "partial_timeout"
    else:
        completion = "failed"

    return {
        "entry_id": entry.id,
        "profile": profile.value,
        "languages": list(entry.languages),
        "window_seconds": [entry.segment_start_seconds, entry.segment_end_seconds],
        "job_final_state": job_state,
        "completion": completion,
        "range_coverage_ratio": round(coverage_ratio, 4),
        "verified_point_count": len(points),
        "point_recall": matched / len(points) if points else 0.0,
        "mean_cer_by_language": {
            language: sum(values) / len(values) for language, values in cer_by_language.items()
        },
        "multilingual_missing_layer_count": missing_total,
        "multilingual_wrong_assignment_count": wrong_assignment_total,
        "user_facing_cue_count": len(cues),
        "observation_count": metrics.observations_created,
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
            "detector_calls": metrics.detector_calls,
            "detector_seconds": round(metrics.detector_seconds, 2),
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

        profile = _PROFILE_BY_ENTRY_ID.get(entry.id)
        if profile is None:
            problems.append(f"{entry.id}: no profile assigned in _PROFILE_BY_ENTRY_ID")

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
        profile_supports_entry = True
        if profile is EvidenceJobProfile.EXPERIMENTAL_HYBRID and multilingual:
            profile_supports_entry = False
            problems.append(
                f"{entry.id}: assigned {EvidenceJobProfile.EXPERIMENTAL_HYBRID.value}, which is "
                f"single-language by construction (build_hybrid_ocr_evidence_job takes one engine), "
                f"but this entry declares {list(entry.languages)}"
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
            "profile": profile.value if profile else None,
            "languages": list(entry.languages),
            "window": [entry.segment_start_seconds, entry.segment_end_seconds],
            "media_duration_seconds": round(duration, 2) if duration is not None else None,
            "roi": [roi.x, roi.y, roi.width, roi.height] if roi else None,
            "ground_truth_cues": len(entry.ground_truth_cues),
            "verified_instants": len(instants),
            "runnable": profile is not None and profile_supports_entry,
        })

    # Deliberately no single top-level "profile" field: this is a
    # split-profile evaluation, and a reader who only looked at one field
    # here could mistake it for the whole run's profile. `profiles_used`
    # names every distinct profile actually assigned below, keyed
    # per-entry in `entries`.
    report = {
        "manifest": str(MANIFEST_PATH),
        "profiles_used": sorted({row["profile"] for row in rows if row["profile"]}),
        "entries": rows,
    }
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
            # Check each entry through the job type it will really use in
            # the real run -- the entry's assigned split-profile entry,
            # single-language build_hybrid_ocr_evidence_job or multilingual
            # build_ocr_evidence_job's shared machinery either way. Both
            # have their own work loop, so verifying only one would leave
            # the other's cancellation path unexercised on these windows.
            entry_profile = _profile_for(entry)
            hybrid = entry_profile is EvidenceJobProfile.EXPERIMENTAL_HYBRID
            job = build_evidence_job_for_profile(
                entry_profile,
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
                "job_profile": entry_profile.value,
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


def _summarize_by_profile(entry_results: list[dict]) -> dict:
    """Per-profile aggregates ONLY -- grouped strictly by which profile
    produced each entry, never combined across profiles. This function
    exists precisely so nothing downstream has to (or can, without
    reaching past it) collapse Hybrid and Production results into one
    number."""
    by_profile: dict[str, list[dict]] = {}
    for row in entry_results:
        by_profile.setdefault(row["profile"], []).append(row)

    summary = {}
    for profile, rows in by_profile.items():
        recalls = [row["point_recall"] for row in rows]
        cer_values: list[float] = []
        for row in rows:
            cer_values.extend(row["mean_cer_by_language"].values())
        ratios = [
            row["performance"]["processing_time_to_media_duration_ratio"]
            for row in rows
            if row["performance"]["media_duration_seconds"] > 0
        ]
        summary[profile] = {
            "entry_count": len(rows),
            "entry_ids": [row["entry_id"] for row in rows],
            "completion_by_entry": {row["entry_id"]: row["completion"] for row in rows},
            "mean_point_recall": sum(recalls) / len(recalls) if recalls else 0.0,
            "mean_cer_across_languages_and_entries": (
                sum(cer_values) / len(cer_values) if cer_values else None
            ),
            "mean_processing_time_to_media_duration_ratio": (
                sum(ratios) / len(ratios) if ratios else None
            ),
            "total_user_facing_cues": sum(row["user_facing_cue_count"] for row in rows),
            "total_observations": sum(row["observation_count"] for row in rows),
        }
    return summary


def run() -> dict | None:
    if not MANIFEST_PATH.exists():
        print(f"No private corpus manifest at {MANIFEST_PATH} -- skipping (this is expected on any machine "
              "without the repo owner's local private_samples/).")
        return None

    app = QApplication.instance() or QApplication([])
    preflight()
    entries = load_corpus_manifest(MANIFEST_PATH)

    entry_results = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for entry in entries:
            video_path = MANIFEST_PATH.parent / entry.video_path
            db_path = Path(tmpdir) / f"{entry.id}.sqlite3"
            if len(entry.languages) > 1:
                metrics, cues, state, profile = _run_multilingual_job(video_path, entry, db_path)
            else:
                metrics, cues, state, profile = _run_single_language_job(video_path, entry, db_path)
            entry_results.append(_evaluate_entry(entry, metrics, cues, state, profile))

    results = {
        "entries": entry_results,
        # Grouped by the profile that actually produced each entry's
        # evidence -- never a single number spanning both. A reader who
        # wants "the" recall or CER for this run must pick a profile
        # group; there is deliberately no cross-profile aggregate to
        # reach for instead.
        "summary_by_profile": _summarize_by_profile(entry_results),
    }
    PRIVATE_RESULTS_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {PRIVATE_RESULTS_PATH} (private, gitignored)")
    return results


# --- M11 stage 5-C completion supplement (2026-09-02 human gate) ----------
#
# The five-window stress run above (`run()`) is COMPLETE and its results
# (`evaluation_results.json`) are final: every window came back
# `partial_timeout` under the 600s per-entry cap, and that finding is kept
# exactly as produced -- nothing below reopens, rewrites, or reruns it.
#
# This supplement asks a narrower, explicitly scoped question: given more
# wall-clock budget, do the two windows already approved for Experimental
# Hybrid (`sample_g`, `sample_e` -- unchanged window and ROI) and the
# pre-existing M10 `sample_a` clean-baseline reserve (reused verbatim, not
# a newly hand-picked segment) actually finish? Hybrid only; the 600s
# five-window run is not touched or repeated; if an entry still times out
# at 1800s, that is reported exactly like any other partial result -- this
# function makes exactly one attempt per entry and does not escalate.

_COMPLETION_SUPPLEMENT_ENTRY_IDS = (
    "private-g-english-handheld",
    "private-e-chinese-screenshare",
    "private-a-clean-zh",
)
_COMPLETION_SUPPLEMENT_TIMEOUT_SECONDS = 1800.0
SUPPLEMENT_RESULTS_PATH = MANIFEST_PATH.parent / "evaluation_results_completion_supplement.json"


class CompletionSupplementPreflightError(RuntimeError):
    """Mirrors `PreflightError` for the completion supplement's own,
    smaller entry set and its two manifest sources."""


def _load_completion_supplement_entries() -> list[CorpusEntry]:
    by_id: dict[str, CorpusEntry] = {}
    if MANIFEST_PATH.exists():
        for entry in load_corpus_manifest(MANIFEST_PATH):
            by_id.setdefault(entry.id, entry)
    if M10_EXPORT_MANIFEST_PATH.exists():
        for entry in load_corpus_manifest(M10_EXPORT_MANIFEST_PATH):
            by_id.setdefault(entry.id, entry)

    entries: list[CorpusEntry] = []
    problems: list[str] = []
    for entry_id in _COMPLETION_SUPPLEMENT_ENTRY_IDS:
        entry = by_id.get(entry_id)
        if entry is None:
            problems.append(
                f"{entry_id}: not found in {MANIFEST_PATH.name} or {M10_EXPORT_MANIFEST_PATH}"
            )
            continue
        if len(entry.languages) != 1:
            problems.append(
                f"{entry_id}: the completion supplement runs Experimental Hybrid, which is "
                f"single-language by construction, but this entry declares {list(entry.languages)}"
            )
        if entry.id not in _ROI_BY_ENTRY_ID:
            problems.append(f"{entry_id}: no ROI in _ROI_BY_ENTRY_ID")
        entries.append(entry)

    if problems:
        bullets = "".join(f"{chr(10)}  - {problem}" for problem in problems)
        raise CompletionSupplementPreflightError(
            "completion supplement preflight failed; nothing was run:" + bullets
        )
    return entries


def run_completion_supplement(
    *, timeout_seconds: float = _COMPLETION_SUPPLEMENT_TIMEOUT_SECONDS
) -> dict | None:
    if not MANIFEST_PATH.exists() or not M10_EXPORT_MANIFEST_PATH.exists():
        print(
            "No private corpus manifest(s) -- skipping the completion supplement "
            "(expected on any machine without the repo owner's local private_samples/)."
        )
        return None

    QApplication.instance() or QApplication([])
    entries = _load_completion_supplement_entries()

    entry_results = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for entry in entries:
            video_path = MANIFEST_PATH.parent / entry.video_path
            db_path = Path(tmpdir) / f"supplement-{entry.id}.sqlite3"
            metrics, cues, state, profile = _run_single_language_job(
                video_path,
                entry,
                db_path,
                profile=EvidenceJobProfile.EXPERIMENTAL_HYBRID,
                timeout_seconds=timeout_seconds,
            )
            entry_results.append(_evaluate_entry(entry, metrics, cues, state, profile))

    results = {
        "kind": "completion_supplement",
        "relationship_to_main_run": (
            "Supplements, does not replace, the five-window stress run in "
            f"{PRIVATE_RESULTS_PATH.name}. That file's five entries -- including this "
            "supplement's sample_g and sample_e as they ran under the 600s timeout -- "
            "are unchanged and untouched by this function."
        ),
        "timeout_seconds": timeout_seconds,
        "entries": entry_results,
        "summary_by_profile": _summarize_by_profile(entry_results),
    }
    SUPPLEMENT_RESULTS_PATH.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Wrote {SUPPLEMENT_RESULTS_PATH} (private, gitignored)")
    return results


if __name__ == "__main__":
    import sys

    if "--preflight" in sys.argv:
        print(json.dumps(preflight(), ensure_ascii=False, indent=2))
    elif "--crash-check" in sys.argv:
        print(json.dumps(crash_condition_check(), ensure_ascii=False, indent=2))
    elif "--completion-supplement" in sys.argv:
        supplement_results = run_completion_supplement()
        if supplement_results is not None:
            print(json.dumps(supplement_results, ensure_ascii=False, indent=2))
    else:
        run_results = run()
        if run_results is not None:
            print(json.dumps(run_results, ensure_ascii=False, indent=2))
