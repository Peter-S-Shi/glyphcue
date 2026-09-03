# GlyphCue — PROJECT_STATUS.md

**Last updated:** 2026-09-03

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
surfaced a correctness finding (Chinese-language CER above 1.0).
This finding served as the historical trigger for the **Caption Identity
Corrective Gate**, which successfully diagnosed the root cause (hybrid state
transition and consensus disambiguation) and integrated formal fixes (843 tests passed).
Subsequently, three major performance hardening gates were integrated:
**P2 Recognition-only Patch**, **P3 Windows-only Opt-in DirectML Recognizer**,
and **P4B Windows-only Opt-in Same-Detector DirectML Text Detector** (`PP-OCRv6_det_medium.onnx`).
Parallel chunking was also evaluated via an evidence gate and formally **REJECTED**
due to thread DirectX/D3D12 device safety and multiprocess lock serialization.
`sample_h`/`sample_f`/`sample_c` coverage remains partial. **Stage ⑤ is still OPEN**
(correctness corrective closed, but representative evaluation gate remains open);
results are recorded in [`docs/m11_representative_evaluation.md`](docs/m11_representative_evaluation.md)
§15–§16, and folded into [`EVALUATION_REPORT.md`](EVALUATION_REPORT.md) and
[`FAILURE_MODE_REPORT.md`](FAILURE_MODE_REPORT.md). M11 is **not** complete and that gate is still open.

**Multilingual Architecture B integrated** (shared detection + universal
recognition, corrective 12-case gate — see
[`docs/multilingual/track_group_reconstruction.md`](docs/multilingual/track_group_reconstruction.md)'s
Milestone 11 Architecture B section). **Stage ⑤ representative evaluation
still open pending post-integration `sample_h`/`sample_f`/`sample_c`
confirmation** — Architecture B landing does not by itself close Stage ⑤.
A real 10s-window post-integration smoke on all three surfaced a genuine,
unresolved **speed/correctness trade-off, not a closed result**: on CPU
Paddle (the shipped default), correctness/layer/timing/review semantics
held (correct script separation, sensible multiline joins, missing/
ambiguous diagnostics firing as documented) but wall time measured
7.4×–14.0× realtime (`sample_h` 13.99×, `sample_f` 7.45×, `sample_c`
9.25×) — a real ~7–15× improvement over the pre-Architecture-B baseline's
~99–159×, but still over the ≤5× target. With the opt-in DirectML
engine+detector (P2/P3/P4B), all three measured well under the ≤5×
target (`sample_h` 2.11×, `sample_f` 2.93×, `sample_c` 3.12×), but that
same run showed real correctness degradation not seen on CPU: multiple
Cues with language content visibly swapped into the wrong layer (e.g.
`sample_h`'s first Cue put an English sentence under `"zh"`), at least
one garbled non-text reading (`sample_c`'s first Cue read `"zh": "3\n8"`
where CPU Paddle read real Chinese text), and roughly 1.5–3× more Cues
produced for the identical window (`sample_h`: 12 CPU vs 21 DirectML)
from noisier per-frame recognition fragmenting otherwise-stable states.
**Update — root cause diagnosed and fixed, gate CLOSED (commit `075ac4b`,
on top of the visual-line script-incompatibility veto in `615b56b`).**
The DirectML-path layer-content errors above were re-diagnosed against
real raw `sample_f` (566–568.4s) observations, not guessed: DirectML's
own detector (P4B, `box_thresh=0.45`, unchanged) correctly produced
separate polygons for the English line and the Chinese line beneath it
— there was no detector under-segmentation. The actual bug was in
`_cluster_by_visual_line` (`language_layer_assignment.py`): a
legitimately mixed Han+Latin OCR reading of the Chinese line (e.g.
`"srs有效的原因是"`, the ASCII substring `"srs"` bleeding into an
otherwise-Chinese transcription) makes `_dominant_script` return `None`
— the same value it returns for genuinely no-signal text like bare
digits. The prior script-incompatibility veto (added in `615b56b`)
treated both as "no evidence, never block a merge", so a few pixels of
real Y-overlap let the mixed-script reading merge into the adjacent
decisive-English cluster and get silently classified `en`. `075ac4b`
adds `_has_mixed_script_evidence` and extends the veto: an observation
carrying real mixed Han+Latin evidence is never absorbed into an
adjacent DECISIVE single-language cluster by geometry alone — it starts
its own cluster, staying fail-closed/ambiguous through the existing
unresolved-cluster fallback exactly like any other no-single-decisive-
script cluster. No new numeric threshold; genuinely no-signal text
(digits/punctuation) is unaffected
(`test_non_decisive_neighbor_never_triggers_a_false_veto` still passes).

TDD red→green: the new regression
(`test_mixed_script_observation_adjacent_to_decisive_neighbor_is_not_absorbed`)
reproduced the exact bug against the pre-fix code, then passed after the
fix. Full targeted Architecture B + visual-line regression (29 tests)
and the whole suite (902 passed, 1 skipped, 1 xfailed) are green; GitHub
Actions CI is green on PR #13 (run `33815414759`).

Re-verified against the real DirectML product path
(`create_ocr_engine(prefer_directml=True)` +
`create_text_detector(prefer_directml=True)`, real
`build_multilingual_ocr_evidence_job` →
`reconstruct_multilingual_cues_for_track_group`) on all three frozen
10s windows (`sample_h` 900–910s, `sample_f` 560–570s, `sample_c`
480–490s), run from a freshly provisioned, disposable `[directml]` venv
(this worktree's own `.venv` only carries the `[ocr]` extra; `[directml]`
is deliberately its own environment per `pyproject.toml`) with the
pinned `rapidocr==3.9.2`/`onnxruntime-directml==1.24.4` confirmed via
`onnxruntime.get_available_providers()` (`DmlExecutionProvider` present)
and both `create_ocr_engine`/`create_text_detector` confirmed to
actually resolve to their DirectML classes before any timing was taken
(the detector needed `PP-OCRv6_det_medium.onnx`, ~59MB, fetched fresh
from the same pinned `v3.9.2` RapidOCR/modelscope registry `pyproject.toml`
already trusts — this environment's model cache was otherwise empty):
- **No layer swap in any window.** `sample_f`'s previously-swapped
  content is now correct: `"srs有效的原因是"` stays in the `zh` layer
  across all four affected Cues (566.3–568.4s) and each is correctly
  flagged `ambiguous_languages = {"zh"}` — fail-closed, not silently
  confident, exactly as designed.
- **Realtime:** `sample_h` 3.47×, `sample_f` 4.51×, `sample_c` 4.80× —
  all ≤5×, though visibly higher than the previously-measured
  2.11×/2.93×/3.12×; this run's model/session cache was cold (first
  inference in a brand-new venv), which plausibly explains the gap. Not
  independently isolated from a warm-cache re-run in this session.
- **`sample_c`'s pre-existing `"zh": "3\n8"` garbled first-Cue reading
  persists unchanged** — correctly flagged ambiguous, not a layer swap,
  and not diagnosed by this fix (out of scope: no detector/threshold
  changes were made). Still a separately open, un-diagnosed item.
- Cue counts this round: `sample_h` 18, `sample_f` 23, `sample_c` 7
  (10s windows). `sample_h`'s 18 sits between the CPU baseline's 12 and
  the pre-veto DirectML bug's 21; this run did not re-baseline against a
  fresh CPU-Paddle control, so fragmentation parity is reported as
  observed, not independently re-confirmed against CPU in this pass.

Per human authorization given with these results in hand, **the
Multilingual Performance Corrective Gate is CLOSED.** This closes the
Corrective Gate specifically — it does not by itself close Stage ⑤
Representative Evaluation (below) or advance PR #13 out of Draft.

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
- **New finding, reported as initially measured:** mean CER on the two
  Chinese-language entries exceeded 1.0 (`sample_e` 1.166, `sample_a`
  1.679) — the recovered text at matched instants diverges from the
  short verified reference by more edits than the reference contains.
  `sample_g`'s English CER (0.163) was normal. While not diagnosed
  during that evaluation run itself, this finding served as the historical
  trigger for the subsequent **Caption Identity Corrective Gate**, which
  formally diagnosed and resolved the root cause in product code.

- `sample_h`/`sample_f`/`sample_c` were **not** re-attempted; their
  stress-run partial results are unchanged.
- Full breakdown, the explicit stress-run-vs-supplement distinction, and
  an extended Human Adjudication list are in
  `docs/m11_representative_evaluation.md` §16.
- Findings folded into `EVALUATION_REPORT.md` ("M11 stage 5 —
  Representative-Video Evaluation") and `FAILURE_MODE_REPORT.md`
  (updated #5, #7; #12 for the CER finding; addendum to #6).

Stage ④ Targeted Regression (CLOSED) remains recorded in
[`docs/m11_targeted_regression.md`](docs/m11_targeted_regression.md):
14 seams, 12 PASS, 2 defects reproduced and fixed, 3 findings recorded and
deliberately left unfixed.

### Product Corrective & Performance Enhancements Integrated in M11

1. **Caption Identity Corrective Gate (CLOSED):**
   - Investigated and resolved the root cause of the Chinese-language CER finding (hybrid state transition and multi-frame consensus disambiguation in `hybrid_evidence_job` / `caption_identity_verification`).
   - Integrated formal fixes into `src/glyphcue/application/`; full regression verified with 843 tests passing.

2. **P2 Recognition-Only Performance Patch (INTEGRATED):**
   - Eliminated duplicate detection when external polygons are already available for representative frames.
   - Introduced `RegionOcrEngine.recognize_regions()` on `PaddleOcrEngine` with safe fallback; achieved ~3.26× E2E speedup on real Hybrid pipelines.

3. **P3 Windows DirectML OCR Recognizer (INTEGRATED):**
   - Added Windows-only, opt-in GPU acceleration for text recognition (`PP-OCRv6_rec_small.onnx`) via `GLYPHCUE_PREFER_DIRECTML_OCR=1`.
   - Included non-importing platform preflight, execution probe, and safe fallback to Paddle CPU.

4. **P4B Same-Detector DirectML Text Detector Acceleration (INTEGRATED):**
   - Pure execution-backend substitution using official `PP-OCRv6_det_medium.onnx` with exact-matching Paddle DBNet pre/post-processing (`limit_side_len=640`, `thresh=0.2`, `box_thresh=0.45`, `unclip_ratio=1.4`, ImageNet normalization).
   - Windows-only, opt-in via `GLYPHCUE_PREFER_DIRECTML_DETECTOR=1`, with safe CPU fallback.
   - No meaningful downstream geometry/evidence drift / sufficient geometry parity (100% subtitle recall, 0.835 mean IoU across 12 diverse frames): 100% subtitle text and timing parity on `sample_g` and `sample_e`, delivering ~1.67–1.79× E2E speedup.

### Architecture Direction Decisions

- **Parallel Chunking Feasibility Gate (REJECTED):**
  Formally evaluated across thread and multiprocess architectures; rejected based on empirical evidence (Direct3D 12 device access violations across threads, multiprocess lock serialization). Parallel chunking is closed and not a pending work item.

## Validation


| Suite | Result |
|---|---|
| `pytest` (targeted P4B selection, contract & UI seams) | **40 passed** in 1.19s |
| `pytest` (whole repository, full suite) | **843 passed, 1 xfailed** in 115s |
| `tests/ui` (one process) | 295 passed, 1 xfailed |
| GitHub Actions CI (`milestone/11-product-hardening-full-regression`) | **All green** (Run 33774773070) |

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
  for `EVALUATION_REPORT.md` as reported, or fuller coverage is required first.
- `sample_f`'s one illegible Chinese layer would change if the gate
  chooses to re-read that frame by hand.
- Packaging hardening (Qt plugins, FFmpeg path, OCR model assets, runtime
  DLLs) — unstarted.
- Formal human Manual QA — unstarted.
- The M11 Full Regression itself — unstarted.

## Next action

The Multilingual Performance Corrective Gate is now CLOSED (see above —
mixed-script adjacency clustering ambiguity was the real root cause, not
detector under-segmentation; fixed in `075ac4b`, re-verified on the real
DirectML product path against all three frozen windows). What remains
open: the `sample_c` `"zh": "3\n8"` garbled reading (separately
un-diagnosed, does not block this gate), and whether `sample_h`'s cue
count is genuine fragmentation vs a legitimate difference from the CPU
baseline (not independently re-confirmed this round). Also pending: the
remaining representative evaluation items
(`docs/m11_representative_evaluation.md` §15–§16), specifically whether
`sample_h`/`sample_f`/`sample_c` receive a timeout extension or whether
existing partial coverage suffices to close the representative gate.
Following Stage ⑤ closure, the
subsequent execution sequence is strictly **Stage ⑥ Full Regression →
Stage ⑦ Formal Human QA** (alongside packaging hardening). Stage ⑤
remains OPEN. Do not treat M11 as complete, and do not advance to
merge-readiness before its earlier stages are signed off. PR #13 stays Draft.
