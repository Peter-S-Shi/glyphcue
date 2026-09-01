# Milestone 10 — Private Representative-Video Corpus: Incident Report

**Status:** the repo owner's realistic private video corpus (`private_samples/m10_video_corpus/`,
gitignored, never committed) is **not evaluated for M10**. The one real
attempt crashed after ~40 minutes of wall clock, exposed a real bug in
the evaluation harness (not the product), and is preserved here as
partial external-realistic evidence and a documented limitation — not
discarded. The controlled/synthetic corpus (see
`docs/m10_performance_diagnosis.md` and
`benchmarks/m10_controlled_video_corpus/`) closes only the reproducible
performance-diagnosis seam; it does **not** satisfy ROADMAP §17's stated
3–5 representative videos × 2–5 minute segments target. That target
remains an explicit, open M10 limitation pending final gate disposition
— it is not waived or silently substituted by the synthetic corpus.

## What was run

`benchmarks/private_video_corpus/run_evaluation.py` against 4 manifest
entries (`private-a-clean-zh`, `private-d-bilingual-typical`,
`private-b-difficult-styled`, `private-c-difficult-mixed-format`), each a
2–5 minute segment of a real, private, copyrighted video the repo owner
supplied locally. The real, unmodified production Path A pipeline
(`build_ocr_evidence_job` / `build_multilingual_ocr_evidence_job`, real
`PaddleOcrEngine`, `ChangeTriggeredOcrPolicy`) was invoked per entry.

## What actually happened

The run did **not** end by a clean, owner-requested cancellation. By the
time cancellation was attempted, the background process had already
crashed on its own (exit code 1) — there was nothing left to cancel.
This corrects an earlier statement made mid-session that samples run
"only ever one job in flight" / strictly sequentially: that description
is only true in the happy path. The real trace shows it is **false**
once a job overruns a wait timeout — see "Root cause" below.

Recovered real evidence (from the four orphaned SQLite files left behind
in the OS temp directory, read directly — the in-process `PipelineMetrics`
objects themselves were never persisted and are lost with the crashed
process; every field below is either read from the database rows
actually written, or from OS-level file timestamps, never estimated):

| Entry | Segment (media) | Real media coverage achieved | Distinct triggered frames | Observations persisted | Job's own wall-clock window (file create → last write) |
|---|---|---|---|---|---|
| private-a-clean-zh | 15.0–192.0s (177s) | 15.0 → 32.53s (17.5s) | 177 | 363 (334 `zh` + 29 blank) | 2404.5s (40.07 min) |
| private-d-bilingual-typical | 20.0–200.0s (180s) | 20.0 → 24.10s (4.1s) | 28 | 110 (54 `en` + 54 `zh` + 2 blank) | 1805.4s |
| private-b-difficult-styled | 270.0–450.0s (180s) | 270.0 → 273.14s (3.1s) | 21 | 82 (40 `en` + 40 `zh` + 2 blank) | 1170.2s |
| private-c-difficult-mixed-format | 480.0–660.0s (180s) | 480.0 → 480.001s (~0s) | 1 | 6 (3 `en` + 3 `zh`) | 375.4s |

**Overall wall clock, first engine construction to crash: 2404.5 seconds
(40.07 minutes)** — the four jobs' file-write windows overlap heavily
(entry `a`'s file was still being written when `d`, `b`, and `c` each
started their own jobs), confirmed by OS file-modify timestamps landing
within ~7 seconds of each other across all four files at the moment of
the crash.

**PipelineMetrics fields not recoverable (marked unavailable, not
estimated):** `ocr_calls` (distinct from triggered-frame count for the
multilingual entries, since each triggered frame costs one call per
language — the exact per-language call count was never persisted
separately from the observation rows it produced), exact
`elapsed_seconds`/`effective_processing_speed`/`ocr_calls_per_minute` as
the job itself would have reported them, and final `JobState` (each job's
Python thread was still inside its work loop, mid-OCR-call, when the
process was torn down — no job ever reached `SUCCEEDED`, `FAILED`, or
`CANCELLED`; `state_changed`/`progress` signal emission itself started
failing with `RuntimeError: Signal source has been deleted` once the
process began exiting, which is itself evidence the Qt object graph was
already being destroyed out from under a still-running worker thread).

**ROI, languages, OCR runtime configuration:** ROI per entry and
languages are recorded in the (private, gitignored)
`private_samples/m10_video_corpus/manifest.json` and in
`benchmarks/private_video_corpus/run_evaluation.py`'s
`_ROI_BY_ENTRY_ID`, both already tracked/described without embedding any
private video content. OCR runtime: real `PaddleOcrEngine`, default
`ChangeTriggeredOcrPolicy`, per ADR 0001/0002 — unchanged, not tuned for
this run.

No private video paths, private frame content, or private OCR-recognized
text left this machine; the numbers above are structural counts and
timestamps only.

## Root cause: an evaluation-harness bug, not a product defect

`benchmarks/private_video_corpus/run_evaluation.py`'s original `_run_job`
helper:

```python
def _run_job(job) -> None:
    loop = QEventLoop()
    job.finished.connect(loop.quit)
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(600_000)
    job.start()
    loop.exec()
    job.wait(timeout=1.0)
```

The `QTimer` timeout only calls `loop.quit()` — it never calls
`job.request_cancel()`. `Job`'s real cooperative-cancellation contract
(`src/glyphcue/jobs/job.py`) requires a caller to call
`request_cancel()` and have the work loop observe
`context.is_cancel_requested()`; nothing in the timeout path did that.
So once a job ran longer than the wait, the script's `for entry in
entries:` loop moved on and started the **next** entry's job (and its
own `PaddleOcrEngine` construction) while the **previous** entry's job
kept running, unbounded, on its own orphaned background thread — turning
an intended strictly-sequential, one-job-at-a-time run into unbounded
concurrent execution once any single entry ran long. This is exactly why
all four temp SQLite files show overlapping write windows, and why
`sample_b`/`sample_c` (started later, competing with earlier orphaned
threads for CPU/GIL) made almost no real progress at all. A second, minor
bug in the same script (`ObservationRepository(connect(db_path))...`
without closing the connection before the `tempfile.TemporaryDirectory`
context tries to delete it) is what turned the eventual crash into an
unhandled `PermissionError` instead of a clean exit.

**This is a bug in the evaluation harness's job-orchestration code, not
in `glyphcue.jobs.Job`, `build_ocr_evidence_job`, or
`build_multilingual_ocr_evidence_job`** — the production cancellation
contract works correctly when actually invoked (verified directly in
`docs/m10_performance_diagnosis.md`'s controlled run, where the fixed
harness cancels an overrunning job cleanly). It is fixed in this same
commit for `benchmarks/private_video_corpus/run_evaluation.py`, mirroring
the fix already applied and verified in
`benchmarks/m10_controlled_video_corpus/run_performance_diagnosis.py`.

The complete absence of live progress reporting (`_run_job` never
subscribed to `job.progress`, despite `Job` emitting it and both evidence
jobs calling `context.report_progress` every frame) compounded the
incident: there was no way to see the run stalling in real time, only a
post-hoc reconstruction from abandoned database files after the fact.
This is also fixed in the same commit.

## Product-pipeline finding, kept distinct from the harness bug

Independent of the concurrency bug, the raw trigger/coverage numbers for
entry `private-a-clean-zh` (177 distinct OCR-triggered frames across only
~17.5 real media-seconds of actual progress) are a real, if
contention-confounded, signal that `ChangeTriggeredOcrPolicy`'s
change-detection threshold triggered far more often on this real,
non-static camera background than on the clean synthetic fixtures it was
originally verified against (ADR 0002 already states this exact
limitation: "does not claim the change-detection threshold is optimal
for... noisy compression artifacts... that would need a larger, more
varied evidence set"). This finding is investigated further, in a
controlled and reproducible way, in `docs/m10_performance_diagnosis.md`.

## Disposition

- The private realistic corpus is **not** re-attempted during M10. Doing
  so safely would require first fixing the harness bugs above (done) and
  separately addressing the underlying performance cost per
  `docs/m10_performance_diagnosis.md` (M11 territory, per that
  document's scope).
- The controlled/synthetic corpus in
  `benchmarks/m10_controlled_video_corpus/` closes only the reproducible
  performance-diagnosis seam of Path A evaluation — it is clearly labeled
  as controlled/synthetic, and is not a substitute for, or equivalent to,
  this realistic private corpus. ROADMAP §17's representative-video
  target (3–5 videos × 2–5 minute segments) is **not** closed by it and
  remains an open M10 limitation / acceptance item, to be dispositioned
  at the M10 gate audit rather than silently waived or moved.
- This incident, and the crashed run's real (if partial) evidence, stand
  as a documented M10 limitation and a real observed failure/finding —
  not discarded as noise.
