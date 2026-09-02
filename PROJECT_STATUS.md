# GlyphCue — PROJECT_STATUS.md

**Last updated:** 2026-09-02

## Current milestone

**Milestone 11 — Product Hardening & Full Regression: IN PROGRESS.**
Currently at stage ④ **Targeted Regression**. M11 is **not** complete and
its acceptance gate (ROADMAP §18), including the representative-video
evaluation transferred from M10 by §17's gate audit, is still open.

Feature Freeze is ACTIVE. Milestones 0–10 are complete and merged
(PRs #1–#12).

## Work completed in this stage

Stage ④ Targeted Regression — a narrow, evidence-driven regression over
the seams this round's Corrective Hardening and Experimental Hybrid
integration touched. Full seam-by-seam evidence:
[`docs/m11_targeted_regression.md`](docs/m11_targeted_regression.md).

- 14 targeted seams verified; 12 PASS, 2 reproduced as real defects and
  fixed.
- Defect 1 — a hand-paused Cue Replay left the A-B preview loop
  suspended indefinitely and kept a dead span armed
  (`PlaybackController`). Fixed by giving a span one exit path.
- Defect 2 — "Discard Latest OCR Run" was entirely outside its
  (horizontally unscrollable) viewport at the window size the app opens
  at, 1280×720. Fixed by laying the four OCR controls out 2×2.
- Three findings reproduced and deliberately **not** fixed (recorded, one
  as a `strict` `xfail`): whole-workbench overflow at the 1024×600
  minimum window size, the 3-decimal ROI spin-box quantization inherited
  from M2, and mutual blocking between two concurrent Qt `pytest`
  processes.

Out of scope for this stage and untouched: no OCR research reopened, no
threshold retuned, the legacy Production path kept, the Experimental
Hybrid profile still developer/manual-QA-only.

## Validation

| Suite | Result |
|---|---|
| `pytest` (whole repository) | **831 passed, 1 xfailed** in 112s |
| `tests/ui` (one process) | 291 passed, 1 xfailed |

New regression evidence: `tests/ui/test_m11_targeted_regression_workspace_seams.py`,
`..._playback_seams.py`, `..._layout_seams.py`.

Privacy check: no secrets, credentials, real user data, personal
identifiers, or absolute local paths in the committed changes; local
media, `private_samples/` and `prompt-drafts/` remain untracked.

## Git / PR status

- Branch: `milestone/11-product-hardening-full-regression`
- PR: [#13](https://github.com/Peter-S-Shi/glyphcue/pull/13) — **Draft**,
  intentionally not ready for review or merge.

## Unresolved

- ROADMAP §18 acceptance gate is open, including gate 9 (the transferred
  representative-video evaluation).
- Packaging hardening (Qt plugins, FFmpeg path, OCR model assets, runtime
  DLLs) — unstarted.
- Formal human Manual QA — unstarted.
- The M11 Full Regression itself — unstarted.

## Next action

Human gate review of stage ④'s evidence, then the next M11 stage. Do not
treat M11 as complete, and do not advance to Full Regression or
merge-readiness before its earlier stages are signed off.
