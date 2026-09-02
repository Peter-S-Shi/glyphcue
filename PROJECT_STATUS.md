# GlyphCue — PROJECT_STATUS.md

**Last updated:** 2026-09-02

## Current milestone

**Milestone 11 — Product Hardening & Full Regression: IN PROGRESS.**
Stage ④ **Targeted Regression is CLOSED** — its automated evidence passed
the human gate on 2026-09-02. Currently at stage ⑤ **Representative
Evaluation**, which is the M10 gate transferred by §17's gate audit
(ROADMAP §18 acceptance gate 9), at step **⑤-B Evaluation Preparation**
(⑤-A corpus selection CLOSED, corpus frozen; ⑤-C harness run not
started). M11 is **not** complete and that gate is still open.

Feature Freeze is ACTIVE. Milestones 0–10 are complete and merged
(PRs #1–#12).

## Work completed in this stage

Stage ⑤ Representative Evaluation. Full detail:
[`docs/m11_representative_evaluation.md`](docs/m11_representative_evaluation.md).

**⑤-A Corpus selection — CLOSED** (accepted at the human gate). Read-only
inventory of all eight private sample videos; corpus frozen at five
3-minute windows: `sample_g` 90–270 s, `sample_e` 150–330 s, `sample_h`
900–1080 s, `sample_f` 560–740 s, `sample_c` 480–660 s. `sample_a` held
as a clean-baseline reserve; `sample_b` and `sample_d` ruled out as
redundant.

**⑤-B Evaluation preparation — IN PROGRESS, this round:**

- One ROI proposal per window, each a validated `ROI` exact at the spin
  boxes' 3 decimals, and each verified by measurement across the whole
  window (451 sampled frames): caption rows carry ink on 100% of frames
  in all five.
- `sample_h`'s fixed footer strip is present on 100% of frames and falls
  **0%** inside its proposed ROI — the exclusion asked for is measured,
  not assumed.
- `sample_g`'s stylized overlay cards **cannot** be fully excluded by a
  rectangle: the card descends to y ≈ 0.85 and the caption's top line
  starts at y ≈ 0.86. Recorded as a measured trade-off with an
  alternative ROI, for the human gate to choose.
- A sparse point-sample ground-truth **candidate** worksheet plus a
  labelled frame-evidence sheet for each of `e` / `f` / `g` / `h` —
  11 candidates each, covering ordinary / short / long captions, line
  changes, fast transitions, blank-gap boundaries, low contrast and
  competing screen text. Every row is `confirmed: false` with empty text
  fields: these are candidates for a human to verify, not ground truth.
  Both live untracked under `private_samples/`.
- `sample_c` keeps its 20 verified M10 ground-truth instants; no manual
  work was duplicated for it.

No evaluation run was started, no OCR or temporal pipeline code was
changed, no threshold retuned, no research reopened. Nothing under `src/`
has been touched by stage ⑤.

Stage ④ Targeted Regression (CLOSED) remains recorded in
[`docs/m11_targeted_regression.md`](docs/m11_targeted_regression.md):
14 seams, 12 PASS, 2 defects reproduced and fixed, 3 findings recorded and
deliberately left unfixed.

## Validation

| Suite | Result |
|---|---|
| `pytest` (whole repository, stage ④) | **831 passed, 1 xfailed** in 112s |
| `tests/ui` (one process, stage ④) | 291 passed, 1 xfailed |

Stage ⑤-A and ⑤-B are documentation and read-only measurement; they
change no product code, so they add no tests and do not invalidate stage
④'s run. Stage ④'s regression evidence remains
`tests/ui/test_m11_targeted_regression_workspace_seams.py`,
`..._playback_seams.py`, `..._layout_seams.py`.

Privacy check: no secrets, credentials, real user data, personal
identifiers, or absolute local paths in the committed changes; local
media, `private_samples/` and `prompt-drafts/` remain untracked. The new
corpus and preparation documents describe the private samples by
structural property only and name no speaker, channel, publication or
brand appearing in them; the ground-truth worksheets and their frame
evidence are written under `private_samples/` and stay untracked.

## Git / PR status

- Branch: `milestone/11-product-hardening-full-regression`
- PR: [#13](https://github.com/Peter-S-Shi/glyphcue/pull/13) — **Draft**,
  intentionally not ready for review or merge.

## Unresolved

- ROADMAP §18 acceptance gate is open, including gate 9 (the transferred
  representative-video evaluation) — stage ⑤ is at corpus selection; no
  evaluation run has been executed.
- Ground truth for `sample_e` / `sample_f` / `sample_g` / `sample_h` is
  proposed but **unconfirmed** — the worksheets need a human pass, or an
  explicit decision to report those four windows qualitatively.
- The five ROI proposals need human confirmation, in particular
  `sample_g`'s card-intrusion trade-off, `sample_e`'s table-intrusion
  trade-off and `sample_h`'s narrow 0.013 bottom margin.
- `run_evaluation.py` reads the corpus manifest from a path where it does
  not currently exist, and the manifest has no entries for the four new
  samples. Left unfixed on purpose: the fix depends on entry ids that are
  not settled yet.
- Packaging hardening (Qt plugins, FFmpeg path, OCR model assets, runtime
  DLLs) — unstarted.
- Formal human Manual QA — unstarted.
- The M11 Full Regression itself — unstarted.

## Next action

Human gate on ⑤-B: confirm the five ROI proposals (including the two
recorded trade-offs), and either fill in the ground-truth worksheets or
decide to report those four windows qualitatively. Then ⑤-C — wire the
manifest and `_ROI_BY_ENTRY_ID`, and run the corpus through
`benchmarks/_job_harness.py`. Do not treat M11 as complete, and do not
advance to Full Regression or merge-readiness before its earlier stages
are signed off. PR #13 stays Draft.
