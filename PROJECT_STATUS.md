# GlyphCue — PROJECT_STATUS.md

**Last updated:** 2026-09-02

## Current milestone

**Milestone 11 — Product Hardening & Full Regression: IN PROGRESS.**
Stage ④ **Targeted Regression is CLOSED** — its automated evidence passed
the human gate on 2026-09-02. Currently at stage ⑤ **Representative
Evaluation**, which is the M10 gate transferred by §17's gate audit
(ROADMAP §18 acceptance gate 9). Steps **⑤-A and ⑤-B are CLOSED**.
**⑤-C has been executed**: the split-profile evaluation approved at its
human gate (Option A — `EXPERIMENTAL_HYBRID` for the two single-language
windows, `PRODUCTION_TRIGGER` for the three bilingual ones) ran against
all five frozen windows with no exceptions. **Every window finished
partial** — each hit the 600 s per-entry timeout before covering its
full 180 s — so **stage ⑤ is NOT closed**; results and a Human
Adjudication list are recorded in
[`docs/m11_representative_evaluation.md`](docs/m11_representative_evaluation.md)
§15. M11 is **not** complete and that gate is still open.

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

No OCR or temporal pipeline code changed; nothing under `src/` has been
touched by stage ⑤ — all of the above is `benchmarks/` harness code plus
untracked private-corpus artifacts.

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
  representative-video evaluation) — stage ⑤'s ⑤-C run is complete but
  every window is partial; four items need human adjudication before
  stage ⑤ can close (`docs/m11_representative_evaluation.md` §15):
  whether to re-run with a longer per-entry timeout (a harness
  parameter, not an algorithm change) given none of the five windows
  finished; `sample_h`'s duplicate-cue risk is inconclusive at only 2.7%
  window coverage; whether the measured Hybrid/Production performance
  gap warrants a controlled follow-up before informing any roadmap
  decision; and whether these partial results are sufficient to fold
  into `EVALUATION_REPORT.md` as reported, or the gate wants fuller
  coverage first.
- `sample_f`'s one illegible Chinese layer would change if the gate
  chooses to re-read that frame by hand.
- Packaging hardening (Qt plugins, FFmpeg path, OCR model assets, runtime
  DLLs) — unstarted.
- Formal human Manual QA — unstarted.
- The M11 Full Regression itself — unstarted.

## Next action

Human adjudication of the four items above
(`docs/m11_representative_evaluation.md` §15), starting with whether the
per-entry timeout should be raised for a fuller-coverage re-run. Do not
treat M11 as complete, and do not advance to Full Regression or
merge-readiness before its earlier stages are signed off. PR #13 stays
Draft.
