# GlyphCue — PROJECT_STATUS.md

**Last updated:** 2026-09-02

## Current milestone

**Milestone 11 — Product Hardening & Full Regression: IN PROGRESS.**
Stage ④ **Targeted Regression is CLOSED** — its automated evidence passed
the human gate on 2026-09-02. Currently at stage ⑤ **Representative
Evaluation**, which is the M10 gate transferred by §17's gate audit
(ROADMAP §18 acceptance gate 9). M11 is **not** complete and that gate is
still open.

Feature Freeze is ACTIVE. Milestones 0–10 are complete and merged
(PRs #1–#12).

## Work completed in this stage

Stage ⑤ Representative Evaluation — **step 1, corpus selection, only.**
Full inventory and candidate matrix:
[`docs/m11_representative_evaluation.md`](docs/m11_representative_evaluation.md).

- Read-only inventory of all eight private sample videos: container facts
  via PyAV, caption language/layer/layout by frame inspection, and a
  pixel-level caption-band cadence profile (occupancy, blank gaps, change
  rate, ink) over one window each.
- Recommended corpus: five 3-minute windows — `sample_g` 90–270 s
  (English-only, handheld, unplated low-contrast serif), `sample_e`
  150–330 s (Chinese-only with dense screen-share text competing with the
  caption band), `sample_h` 900–1080 s (bilingual with a fixed 25-minute
  footer overlay, deep into a long timeline), `sample_f` 560–740 s
  (fastest cadence, dense but intermittent, dynamic background), and
  `sample_c` 480–660 s (caption position/format change, M10 continuity).
- `sample_a` held as a clean-baseline reserve; `sample_b` and `sample_d`
  ruled out as redundant against the five, with reasons recorded.
- Nothing under `src/` was touched. No evaluation run, no OCR algorithm
  change, no threshold retuning, no research reopened.

Stage ④ Targeted Regression (CLOSED) remains recorded in
[`docs/m11_targeted_regression.md`](docs/m11_targeted_regression.md):
14 seams, 12 PASS, 2 defects reproduced and fixed, 3 findings recorded and
deliberately left unfixed.

## Validation

| Suite | Result |
|---|---|
| `pytest` (whole repository, stage ④) | **831 passed, 1 xfailed** in 112s |
| `tests/ui` (one process, stage ④) | 291 passed, 1 xfailed |

Stage ⑤'s corpus-selection step is documentation and read-only
measurement; it changes no product code, so it adds no tests and does not
invalidate stage ④'s run. Stage ④'s regression evidence remains
`tests/ui/test_m11_targeted_regression_workspace_seams.py`,
`..._playback_seams.py`, `..._layout_seams.py`.

Privacy check: no secrets, credentials, real user data, personal
identifiers, or absolute local paths in the committed changes; local
media, `private_samples/` and `prompt-drafts/` remain untracked. The new
corpus document describes the private samples by structural property only
and names no speaker, channel, publication or brand appearing in them.

## Git / PR status

- Branch: `milestone/11-product-hardening-full-regression`
- PR: [#13](https://github.com/Peter-S-Shi/glyphcue/pull/13) — **Draft**,
  intentionally not ready for review or merge.

## Unresolved

- ROADMAP §18 acceptance gate is open, including gate 9 (the transferred
  representative-video evaluation) — stage ⑤ is at corpus selection; no
  evaluation run has been executed.
- No ground truth exists yet for the `sample_e` / `sample_f` /
  `sample_g` / `sample_h` windows, and no per-window ROI has been
  proposed.
- Packaging hardening (Qt plugins, FFmpeg path, OCR model assets, runtime
  DLLs) — unstarted.
- Formal human Manual QA — unstarted.
- The M11 Full Regression itself — unstarted.

## Next action

Human gate confirmation of the five recommended evaluation windows and
their framing, then the rest of stage ⑤ (ground-truth decision, per-window
ROI, then the runs through `benchmarks/_job_harness.py`). Do not treat M11
as complete, and do not advance to Full Regression or merge-readiness
before its earlier stages are signed off. PR #13 stays Draft.
