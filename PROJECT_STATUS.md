# GlyphCue — PROJECT_STATUS.md

**Last updated:** 2026-09-02

## Current milestone

**Milestone 11 — Product Hardening & Full Regression: IN PROGRESS.**
Stage ④ **Targeted Regression is CLOSED** — its automated evidence passed
the human gate on 2026-09-02. Currently at stage ⑤ **Representative
Evaluation**, which is the M10 gate transferred by §17's gate audit
(ROADMAP §18 acceptance gate 9). Steps **⑤-A and ⑤-B are CLOSED**;
**⑤-C is READY but not started**, and is blocked for three of the five
windows (see Unresolved). M11 is **not** complete and that gate is still
open.

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

**⑤-C Evaluation preflight — READY, nothing run:**

- Manifest path inconsistency resolved: the canonical
  `private_samples/m10_video_corpus/manifest.json` now exists with
  exactly the five frozen entries; the M10 export copy is untouched and
  read by nothing.
- `_ROI_BY_ENTRY_ID` extended with the four new entry ids at exactly the
  approved ROI values; preflight fails if ids and manifest ever disagree.
- `EVALUATION_PROFILE` frozen at `EXPERIMENTAL_HYBRID` as a named
  constant, with a real detector constructed and shut down per entry.
- New `--preflight` and `--crash-check` entry points; `run()` now refuses
  to start unless preflight passes. Both no-op without the private corpus,
  so CI and fresh clones are unaffected.
- Preflight structural checks: 5/5 on manifest load, video presence, ROI
  presence, range resolution against real probed duration, and
  ground-truth placement inside the window.
- **M10 crash condition re-verified against all five windows and does
  NOT reproduce**: every job overran a deliberate 1 s timeout, was
  cancelled to a terminal `cancelled` state, left no worker thread alive,
  reported live progress, and the temp directory deleted cleanly. Both
  job types exercised (hybrid where the profile supports the entry,
  production where it does not). No harness defect found, so nothing was
  fixed and no new test was added.

No evaluation run was started. No OCR or temporal pipeline code changed;
nothing under `src/` has been touched by stage ⑤.

Stage ④ Targeted Regression (CLOSED) remains recorded in
[`docs/m11_targeted_regression.md`](docs/m11_targeted_regression.md):
14 seams, 12 PASS, 2 defects reproduced and fixed, 3 findings recorded and
deliberately left unfixed.

## Validation

| Suite | Result |
|---|---|
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
  representative-video evaluation) — stage ⑤ is at corpus selection; no
  evaluation run has been executed.
- **⑤-C is blocked for three of five windows.** `EXPERIMENTAL_HYBRID` is
  single-language by construction (`build_hybrid_ocr_evidence_job` takes
  one engine), but `sample_h`, `sample_f` and `sample_c` are bilingual.
  Preflight refuses the run rather than picking a language on the
  caller's behalf. Three options with their costs are set out in
  `docs/m11_representative_evaluation.md` §13; the recommendation is a
  split profile (Hybrid on the two single-language windows, production
  trigger on the three bilingual ones). Not implemented — the choice is
  the gate's.
- `sample_f`'s one illegible Chinese layer would change if the gate
  chooses to re-read that frame by hand.
- Packaging hardening (Qt plugins, FFmpeg path, OCR model assets, runtime
  DLLs) — unstarted.
- Formal human Manual QA — unstarted.
- The M11 Full Regression itself — unstarted.

## Next action

Decide how the frozen Experimental Hybrid profile should handle the three
bilingual windows (§13), then start ⑤-C:
`python -m benchmarks.private_video_corpus.run_evaluation`. Do not treat
M11 as complete, and do not advance to Full Regression or
merge-readiness before its earlier stages are signed off. PR #13 stays
Draft.
