# Milestone 11 — Hardening Audit & Execution Plan

**Status: read-only audit. No production code changed to produce this
document.** Written before any M11 implementation, per ROADMAP.md §18's
scope and the M11 kickoff instruction to audit before touching production
code. Grounded in already-accepted M10 evidence
(`EVALUATION_REPORT.md`, `FAILURE_MODE_REPORT.md`,
`docs/m10_performance_diagnosis.md`, `docs/m10_private_corpus_incident.md`)
plus direct inspection of the current production code for the specific
areas ROADMAP §18 names (job cleanup, cancellation/failure integrity,
SQLite/thread ownership, progress/ETA observability, repeated OCR
initialization, memory/resource lifecycle, export/reopen,
migrations/settings, packaging seams). No theoretical possibility is
recorded as a blocker without either an M10 evidence citation or a direct
code citation from this audit.

## Confirmed defects

**None found.** This audit did not surface a new correctness defect in
production code. The areas most likely to hide one — job resource
cleanup and cancellation — were inspected directly and found already
correct:

- `build_ocr_evidence_job` / `build_multilingual_ocr_evidence_job`
  (`src/glyphcue/application/ocr_evidence_job.py:100-211`,
  `multilingual_ocr_evidence_job.py`) acquire the OCR engine, DB
  connection, and media source inside one `try`/`finally` and release all
  three, in every exit path (success, cancel-triggered `return`, or
  exception) — this is the correct pattern the M10 evaluation-harness bug
  (`docs/m10_private_corpus_incident.md`) violated; production code never
  had that bug.
- `apply_migrations` (`src/glyphcue/persistence/migrations.py`) is
  idempotent (skips already-applied versions) and transactional (a
  failed migration rolls back both the schema change and its version
  record together, so a retry is always clean). No hardening work
  identified here.
- Non-destructive export (`Pysubs2SubtitleFormatAdapter`) already has
  atomic write, source-overwrite refusal, and `REJECTED`-Cue exclusion
  (M7, `docs/qa/reconstruction_qa_review_priority.md`) — no new gap found.

Known, already-tracked limitations (Review Priority's `low_confidence_only`
miss, Path B's by-design non-resolution of ambiguous transitions, etc.)
remain exactly as recorded in `FAILURE_MODE_REPORT.md` — not re-litigated
here, and not confirmed as M11-actionable defects unless a specific M11
task below says otherwise.

## Confirmed performance bottlenecks

1. **PaddleOCR's ~3s/call recognition latency** (mean 2.9–3.3s, p95
   3.7–6.4s, `docs/m10_performance_diagnosis.md`) — the dominant,
   structural cost of the whole pipeline. Confirmed, already isolated.
2. **`ChangeTriggeredOcrPolicy`'s real-world trigger rate** — 177
   triggers over ~17.5s of real media in the one partial private-corpus
   entry, vs. 3–8 triggers over 5.9s on controlled synthetic fixtures
   (`docs/m10_private_corpus_incident.md`, `docs/m10_performance_diagnosis.md`).
   Confirmed by partial real evidence, consistent with ADR 0002's own
   stated calibration limitation.
3. **OCR runtime/model lifetime ownership — the production job
   lifecycle re-initializes the real Paddle model on every "Run OCR"
   click, not just a lightweight Python object — new finding from this
   audit, not previously recorded.**
   `PaddleOcrEngine.__init__()` (`src/glyphcue/adapters/paddleocr_engine.py:76-83`)
   is cheap — it only validates the language code and sets
   `self._engine = None`. The expensive work is `initialize()`
   (`paddleocr_engine.py:85-91`), which actually constructs the Paddle
   model/runtime (`_construct_paddleocr`), and `shutdown()`
   (`paddleocr_engine.py:132-133`) simply drops that reference. Both
   `build_ocr_evidence_job` and `build_multilingual_ocr_evidence_job`
   (`src/glyphcue/application/ocr_evidence_job.py:100-211`,
   `multilingual_ocr_evidence_job.py`) **own the engine's full
   `initialize()`/`shutdown()` lifecycle themselves, inside each job's own
   `try`/`finally`** — so every job run re-initializes the real model from
   scratch and tears it down again when that job ends, regardless of
   whether `PathAMediaPane._on_run_ocr_clicked`
   (`src/glyphcue/ui/path_a_media_pane.py:530-558`) constructs a fresh
   `PaddleOcrEngine` Python object or reuses one. **A caller-side
   memoization of the `PaddleOcrEngine` instance would not by itself
   eliminate repeated model initialization**, because the object's own
   lifecycle contract (own it, initialize it, shut it down) is exercised
   fresh by the job on every run either way. `create_path_a_app`
   (`src/glyphcue/ui/app.py:172`) wires `ocr_engine_factory=PaddleOcrEngine`
   with no reuse layer at all, so a user re-running OCR twice on the same
   video, or on two videos in the same language within one app session,
   pays PaddleOCR's full construction cost (ADR 0001: 4.57s
   import+construction, warm-up excluded) again from scratch every time,
   multiplied by the number of configured languages for a multilingual
   Track Group. This is exactly the "repeated OCR initialization" item
   ROADMAP §18 already names, and directly overlaps
   `docs/m10_performance_diagnosis.md`'s ranked candidate #3
   ("runtime/model reuse across languages") — this audit extends that
   finding from "across languages within one run" to "across repeated
   runs within one app session," and reframes the fix as an **OCR
   runtime/model lifetime *ownership* change** (who initializes/shuts
   down the engine and when — the job, or a longer-lived session-level
   owner), not a simple object-cache. Any such redesign must preserve:
   failure/cancel cleanup (an engine must still be torn down correctly on
   a failed or cancelled run), correct behavior on app shutdown (no
   orphaned Paddle runtime left alive after the app closes), correct
   behavior when the user switches languages (a session-level engine for
   a no-longer-selected language must not be silently kept alive
   indefinitely, nor torn down and rebuilt on every incidental
   re-selection), and safety against unsafe simultaneous use of one
   engine instance (no two jobs may call `recognize()` on the same shared
   engine concurrently). Not implemented in this corrective — this entry
   only reframes the finding accurately; Phase 1 item 1 below is updated
   to match.

## Reliability risks

1. **No full-pipeline memory or CPU instrumentation exists anywhere.**
   Already recorded as an evidence gap in `EVALUATION_REPORT.md`
   ("Performance" / "Limitations"); this audit confirms it is also a
   reliability blind spot for M11's own "leaks / runaway memory" hardening
   item (ROADMAP §18) — there is currently no instrument in place that
   could even detect a leak if introduced. Addressing this is a
   prerequisite for closing that hardening item with real evidence rather
   than an unverified assertion.
2. **Adaptive chunking / bounded parallelism does not exist yet, and per
   the M11 kickoff instruction is conditional, not a requirement.** If it
   is introduced, the M10 private-corpus incident is a real, direct
   precedent for what to guard against: the orphaned-thread bug produced
   genuine, observed CPU/GIL contention between concurrently-running jobs
   (`docs/m10_private_corpus_incident.md`, "Root cause" — `sample_b`/`sample_c`
   "made almost no real progress at all" while competing with an earlier
   orphaned thread). Any future bounded-parallelism design must be
   evaluated against this precedent specifically, not a hypothetical one.
3. **Progress observability is already adequate in production; ETA is
   not implemented.** `Job.progress` is wired end-to-end in the real UI
   (`PathAMediaPane._on_ocr_progress`, `src/glyphcue/ui/path_a_media_pane.py:580-584`),
   showing real `processed_seconds` / `total_seconds` and a running OCR-call
   count — unlike the evaluation harness's now-fixed gap
   (`benchmarks/_job_harness.py`), production was never silently blind to
   a long-running job's progress. But nothing computes or displays an
   estimated time remaining from that progress stream today — no gap
   requiring urgent hardening, since raw processed/total seconds already
   let a user judge how far a job has gotten, but a real, low-risk M11
   observability candidate (see Phase 2 below), not something to claim as
   already fully closed.
4. **Cancellation contract is already correct in production `Job`**
   (`src/glyphcue/jobs/job.py`) — the bug the M10 incident found and fixed
   was confined to the evaluation harness's own re-implementation of a
   timeout/cancel loop, never in `Job` itself. This audit found no
   production caller with an equivalent bug. Confirmed low risk, not a
   gap requiring new work — regression coverage should simply re-verify
   this holds during the M11 full-suite run.

## Packaging risks

**Confirmed: packaging work has not started at all.** No
`pyside6-deploy` or Nuitka configuration exists anywhere in
`pyproject.toml` or the repository. ADR 0001 already flagged PaddleOCR's
~590MB installed footprint as a real, accepted cost that "will materially
increase installer size and first-run disk usage" and named this
explicitly as Milestone 11 territory. ROADMAP §18's packaging-hardening
scope (Qt plugins, FFmpeg path, OCR model assets, runtime DLLs, local
resource paths) is the single largest wholly-unaddressed item in this
audit — not a risk of regression, but a risk of running out of milestone
time if sequenced too late.

## Evidence gaps (carried from M10, restated for M11 planning — not re-litigated)

- The transferred representative-video evaluation itself (ROADMAP §17/§18,
  mandatory M11 gate — see "Proposed execution order" below).
- WER (any corpus), Path A Cue-level precision/recall, Path A timing
  start/end error, multilingual layer-assignment correctness on real
  material, CPU utilization, full-pipeline memory — all stated as **not
  empirically closed** in `EVALUATION_REPORT.md`; M11 does not
  automatically close these just by doing hardening work, and none is
  assumed closed by anything in this document.
- ROADMAP §18 also names "settings" under both Automated regression and
  Migrations scope. No settings feature exists anywhere in the codebase
  (`DESIGN.md` explicitly lists "Advanced Settings" under its scope
  prohibitions — "no CV tuning exposed by default" — and ROADMAP itself
  scopes settings migrations to "settings required by actual
  implementation," of which there are currently none). This is not a gap
  requiring new work; it is a vacuously-satisfied regression item, noted
  here so it is not mistaken for an oversight during the M11 full-suite
  run.

## Proposed M11 execution order (evidence-first, lowest-risk-first)

**Phase 1 — Low-risk performance levers**, each measured against
`benchmarks/m10_controlled_video_corpus/` and the preserved
`performance_diagnosis_results.json` baseline (before/after), never
against reconstruction correctness in isolation:

1. **OCR runtime/model lifetime ownership hardening** — redesign who owns
   the `PaddleOcrEngine.initialize()`/`shutdown()` lifecycle (currently
   each job, fully, every run) so a session-level owner can reuse an
   already-initialized model across repeated "Run OCR" invocations in one
   app session, instead of a simple instance cache (an object cache alone
   would not eliminate repeated model initialization — see "Confirmed
   performance bottlenecks" #3 above). The design must preserve
   failure/cancel cleanup, correct app-shutdown teardown, correct
   behavior across language switches, and safety against unsafe
   simultaneous use of one engine instance across jobs. Lowest risk of
   the three Phase 1 items in the sense that it changes no reconstruction
   algorithm at all, but it does change job/engine ownership, so it needs
   its own dedicated cancellation/lifecycle regression coverage, not just
   a performance measurement.
2. `ChangeTriggeredOcrPolicy` trigger-rate calibration review against
   less-static controlled fixtures (M10 diagnosis candidate #1).
3. ROI size/downscale cost reduction (M10 diagnosis candidate #2),
   re-verified against ADR 0001's CER evidence so accuracy is not
   silently traded away for speed.

**Phase 2 — Reliability/lifecycle hardening (TDD):**

4. Add full-pipeline memory/CPU instrumentation — closes the evidence gap
   above and gives M11's "leaks / runaway memory" acceptance item
   something concrete to check against.
5. Re-verify job cleanup / cancellation integrity and export/reopen via
   the M11 full regression suite; no new implementation is anticipated
   here unless the suite surfaces something this audit missed.
6. **ETA estimation from the existing `Job.progress` stream** — a real,
   low-risk observability candidate (see "Reliability risks" #3 above):
   progress data (`processed_seconds` / `total_seconds`) already exists
   in production, so this is a display/derivation addition on top of an
   existing signal, not a new instrumentation seam. Not required for M11
   to pass; included here because it is genuinely low-risk and directly
   improves the "representative long jobs" experience Phase 3's decision
   partly depends on.

**Phase 3 — Conditional performance path (only if Phase 1–2 still leave
representative long jobs operationally unacceptable):** adaptive logical
chunking / bounded parallelism, under the constraints already stated in
the M11 kickoff (logical `ProcessingRange` chunks, not physical video
splitting; temporal overlap for consensus/reconstruction context;
deterministic boundary reconciliation; concurrency bounded by CPU/RAM/OCR
cost; cancellation/progress preserved; completed chunks recoverable). Not
started unless Phase 1–2 evidence shows it is actually needed.

**Phase 4 — Representative-video re-attempt (mandatory M11 gate,
ROADMAP §17/§18):** only once the controlled-fixture performance/reliability
baseline is materially improved and stable. Uses the already-hardened
evaluation harness (`benchmarks/_job_harness.py`). Results — whatever they
are, including further negative or partial findings — are folded back
into `EVALUATION_REPORT.md` and, where relevant, `FAILURE_MODE_REPORT.md`,
honestly, per the same discipline M10's own evidence was held to.

**Phase 5 — Packaging hardening:** Qt plugins, FFmpeg path, OCR model
asset bundling, runtime DLLs, local resource paths. Sequenced after the
performance/reliability phases (it does not block generating evidence for
them) but must complete before M11's gate closes — flagged early in this
plan specifically because it is currently unstarted (see "Packaging
risks" above) and should not be left until the end of the milestone by
default.

**Phase 6 — Formal human Manual QA:** deliberately last, once automated
and performance hardening have converged enough that manual QA is
validating a release-quality candidate rather than rediscovering already-
known engineering problems.

**Phase 7 — Full regression + gate closure:** run the complete automated
suite (Path A, Path B, persistence, jobs, export, cancellation,
migrations, settings [vacuous, see above], packaging seams) and close out
ROADMAP §18's acceptance gate, including its mandatory item 9 (the
transferred representative-video evaluation).

## What this document does not do

No production code was changed. No new benchmark was run beyond what M10
already committed. No decision is made here about whether Phase 3
(adaptive chunking/parallelism) will actually be needed — that is
evidence-gated on Phase 1–2's real results, per the M11 kickoff's own
instruction not to treat it as an automatic requirement.
