# GlyphCue — PROJECT_STATUS.md

**Last updated:** 2026-09-02

## Current milestone

**Milestone 11 — Product Hardening & Full Regression: IN PROGRESS.**
Stage ④ **Targeted Regression is CLOSED** — its automated evidence passed
the human gate on 2026-09-02. Currently at stage ⑤ **Representative
Evaluation**, which is the M10 gate transferred by §17's gate audit
(ROADMAP §18 acceptance gate 9). Steps **⑤-A and ⑤-B are CLOSED**.
**⑤-C has been executed, twice.** The split-profile stress run approved
at its human gate (Option A — `EXPERIMENTAL_HYBRID` for the two
single-language windows, `PRODUCTION_TRIGGER` for the three bilingual
ones) ran against all five frozen windows with no exceptions; **every
window finished partial** at the 600 s per-entry timeout. A subsequent,
narrowly-scoped **completion supplement** (human-gate approved) then gave
`sample_g`, `sample_e` and the pre-existing M10 `sample_a` reserve a
1800 s timeout under Hybrid only — **all three completed** — but
surfaced a new, undiagnosed correctness finding (Chinese-language CER
above 1.0). `sample_h`/`sample_f`/`sample_c` were not re-attempted and
remain partial. **Stage ⑤ is still NOT closed**; both runs' results and
Human Adjudication lists are recorded in
[`docs/m11_representative_evaluation.md`](docs/m11_representative_evaluation.md)
§15–§16, and folded into
[`EVALUATION_REPORT.md`](EVALUATION_REPORT.md) and
[`FAILURE_MODE_REPORT.md`](FAILURE_MODE_REPORT.md). M11 is **not**
complete and that gate is still open.

Feature Freeze is ACTIVE. Milestones 0–10 are complete and merged
(PRs #1–#12).

## Work completed in this stage

Stage ⑤ Representative Evaluation. Full detail:
[`docs/m11_representative_evaluation.md`](docs/m11_representative_evaluation.md).

**⑤-A Corpus selection — CLOSED.** Corpus frozen at five 3-minute
windows: `sample_g` 90–270 s, `sample_e` 150–330 s, `sample_h`
900–1080 s, `sample_f` 560–740 s, `sample_c` 480–660 s. `sample_a` held
as a clean-baseline reserve; `sample_b` and `sample_d` ruled out as
redundant.

**⑤-B Evaluation preparation — CLOSED.** All five ROI proposals approved
unchanged at the human gate, and all 44 ground-truth candidates confirmed
with no corrections. Confirmed ground truth: 72 point-sample cues across
52 verified instants (`g` 11, `e` 10, `h` 20, `f` 21, `c` 20 inherited),
plus 2 verified negative points that deliberately emit no cue. One
`sample_f` instant carries only its English layer — its Chinese layer is
illegible in the frame and was left untranscribed rather than guessed.

**⑤-C Split-profile evaluation — RUN COMPLETE, awaiting adjudication:**

- Manifest path inconsistency resolved: the canonical
  `private_samples/m10_video_corpus/manifest.json` now exists with
  exactly the five frozen entries; the M10 export copy is untouched and
  read by nothing.
- `_ROI_BY_ENTRY_ID` extended with the four new entry ids at exactly the
  approved ROI values; preflight fails if ids and manifest ever disagree.
- `_PROFILE_BY_ENTRY_ID` replaces the earlier single frozen profile:
  `EXPERIMENTAL_HYBRID` for `sample_g`/`sample_e`, `PRODUCTION_TRIGGER`
  for `sample_h`/`sample_f`/`sample_c`, per the ⑤-C human gate's approval
  of Option A. Preflight requires every manifest entry to have an
  assigned profile and refuses a multilingual entry assigned Hybrid.
  Results record the actual profile per entry, and a
  `_summarize_by_profile` step aggregates strictly within each profile —
  nothing merges a Hybrid and a Production result into one number.
- New `--preflight` and `--crash-check` entry points; `run()` refuses to
  start unless preflight passes. Both re-confirmed **5/5 windows
  runnable** under the split profile, and the crash-check re-verified
  the M10 incident does not reproduce (clean cancellation, no orphaned
  thread) on all five real windows.
- **The real evaluation ran to completion (exit code 0, no exceptions)
  against real video and real OCR/detector models.** Every one of the
  five windows came back `partial_timeout`: each hit the 600 s per-entry
  cap before finishing its 180 s window (coverage 2.2%–60.9%). This
  reproduces, on real footage, the exact performance cost
  `docs/m10_performance_diagnosis.md` already diagnosed — reported
  honestly, not retried with a longer timeout to get a better number.
- **By profile (never merged):** Hybrid (`sample_g`, `sample_e`) — mean
  point recall 52.7%, mean realtime ratio 6.2×. Production
  (`sample_h`, `sample_f`, `sample_c`) — mean point recall 9.7%, mean
  realtime ratio 128.8×. The gap is real and consistent within each
  group, but the two groups are also different content (single- vs.
  multi-language), so it is reported as a signal for a future controlled
  comparison, not a conclusion about promoting either profile.
- Full per-window table and the Human Adjudication list are in
  `docs/m11_representative_evaluation.md` §15.

**Completion supplement (human-gate approved, strictly scoped) — RUN
COMPLETE:**

- New `run_completion_supplement()` / `--completion-supplement`: Hybrid
  only, 1800 s per-entry timeout, exactly three entries —
  `sample_g`/`sample_e` at their unchanged ⑤-A/⑤-B window and ROI, plus
  the pre-existing M10 `sample_a` clean-baseline reserve reused verbatim
  (window, ROI, ground truth all from the M10 export manifest,
  unchanged). A dedicated preflight-equivalent check refuses to run any
  entry not single-language or missing a manifest/ROI. Writes to a
  **separate** results file
  (`evaluation_results_completion_supplement.json`) — the five-window
  stress run's own results file is never opened or touched by this path.
- **All three completed** (`succeeded`, not a timeout cancellation):
  point recall 90–100% across 31 verified instants. Total wall clock
  74.5 min; no exceptions.
- **New finding, reported as measured:** mean CER on the two
  Chinese-language entries exceeded 1.0 (`sample_e` 1.166, `sample_a`
  1.679) — the recovered text at matched instants diverges from the
  short verified reference by more edits than the reference contains.
  `sample_g`'s English CER (0.163) is normal. A plausible mechanism is
  noted (Hybrid's "one recognition per state" possibly merging a wider
  span than one caption) but explicitly **not investigated or diagnosed**
  this round, per the instruction not to reopen OCR/temporal work.
- `sample_h`/`sample_f`/`sample_c` were **not** re-attempted; their
  stress-run partial results are unchanged.
- Full breakdown, the explicit stress-run-vs-supplement distinction, and
  an extended Human Adjudication list are in
  `docs/m11_representative_evaluation.md` §16.
- Findings folded into `EVALUATION_REPORT.md` ("M11 stage 5 —
  Representative-Video Evaluation") and `FAILURE_MODE_REPORT.md`
  (updated #5, #7; new #12 for the CER finding; addendum to #6).

No OCR or temporal pipeline code changed; nothing under `src/` has been
touched by stage ⑤ — all of the above is `benchmarks/` harness code plus
untracked private-corpus artifacts.

Stage ④ Targeted Regression (CLOSED) remains recorded in
[`docs/m11_targeted_regression.md`](docs/m11_targeted_regression.md):
14 seams, 12 PASS, 2 defects reproduced and fixed, 3 findings recorded and
deliberately left unfixed.

**M11 P4B DirectML Text Detector Acceleration (Opt-in, Windows-only) — INTEGRATED:**
- Integrated `DirectMlTextDetector` backed by official ONNX `PP-OCRv6_det_medium.onnx`
  with exact-matching PaddleDBNet pre/post-processing (`limit_side_len=640`, `thresh=0.2`,
  `box_thresh=0.45`, `unclip_ratio=1.4`, ImageNet normalization).
- Pure execution-backend substitution with zero geometry/word fragmentation drift
  (100% subtitle recall, 0.835 mean IoU across 12 difficult multi-language frames).
- Real hybrid pipeline A/B: 100% subtitle text and timing parity across `sample_g`
  and `sample_e`, delivering ~1.67–1.79× E2E speedup.
- Strict opt-in via `GLYPHCUE_PREFER_DIRECTML_DETECTOR=1` (or `GLYPHCUE_PREFER_DIRECTML_OCR=1`);
  unconditional safe fallback to shipped PaddlePaddle CPU detector on non-Windows,
  missing dependencies, or provider failure.
- Scheduler, Beta-S, 0.300 clustering, caption identity, and P2/P3 recognizers frozen.

## Validation

| Suite | Result |
|---|---|
| `pytest` (targeted P4B selection, contract & UI seams) | **40 passed** in 1.19s |
| `pytest` (whole repository, stage ④) | **831 passed, 1 xfailed** in 112s |
| `tests/ui` (one process, stage ④) | 291 passed, 1 xfailed |


Stage ⑤ changed no product code — only `benchmarks/`, docs and untracked
private corpus files — so it adds no tests. The suite was re-run in full
after the harness changes. Stage ④'s regression evidence remains
`tests/ui/test_m11_targeted_regression_workspace_seams.py`,
`..._playback_seams.py`, `..._layout_seams.py`.

Privacy check: no secrets, credentials, real user data, personal
identifiers, or absolute local paths in the committed changes; local
media, `private_samples/` and `prompt-drafts/` remain untracked. The new
corpus, preparation and preflight documents describe the private samples
by structural property, counts and metrics only, and name no speaker,
channel, publication or brand appearing in them. Every artifact carrying
real content — the corpus manifest with its confirmed caption text, the
ground-truth worksheets, the frame-evidence sheets and the videos — is
written under `private_samples/` and stays untracked. No caption text
appears anywhere in the repository.

## Git / PR status

- Branch: `milestone/11-product-hardening-full-regression`
- PR: [#13](https://github.com/Peter-S-Shi/glyphcue/pull/13) — **Draft**,
  intentionally not ready for review or merge.

## Unresolved

- ROADMAP §18 acceptance gate is open, including gate 9 (the transferred
  representative-video evaluation). `sample_g`/`sample_e`/`sample_a` are
  now fully evaluated (completion supplement); `sample_h`/`sample_f`/
  `sample_c` remain partial at 2.2%–3.5% window coverage. Human
  adjudication needed (`docs/m11_representative_evaluation.md` §15–§16):
  (1) whether to extend the timeout for `sample_h`/`sample_f`/`sample_c`
  too (a harness parameter, not an algorithm change), and if so how far,
  given Production's measured ~99–159× realtime cost; (2) `sample_h`'s
  duplicate-cue risk is still inconclusive; (3) whether the
  Hybrid/Production performance gap warrants a controlled follow-up;
  (4) whether the current partial + supplement results are sufficient
  for `EVALUATION_REPORT.md` as reported, or fuller coverage is required
  first; (5) **new** — the Chinese-language CER > 1.0 finding from the
  completion supplement needs a priority/timeline decision (investigate
  now vs. defer), since nothing in this pass diagnosed or fixed it.
- `sample_f`'s one illegible Chinese layer would change if the gate
  chooses to re-read that frame by hand.
- Packaging hardening (Qt plugins, FFmpeg path, OCR model assets, runtime
  DLLs) — unstarted.
- Formal human Manual QA — unstarted.
- The M11 Full Regression itself — unstarted.

## Next action

Human adjudication of the five items above
(`docs/m11_representative_evaluation.md` §15–§16), starting with the
Chinese-language CER finding's priority and whether
`sample_h`/`sample_f`/`sample_c` get their own timeout extension. Do not
treat M11 as complete, and do not advance to Full Regression or
merge-readiness before its earlier stages are signed off. PR #13 stays
Draft.
