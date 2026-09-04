# Milestone 11 — Representative Evaluation (stage ⑤)

**Status:** CLOSED by Human Adjudication (2026-09-03). All five frozen
representative windows now carry full 180 s evaluation evidence. The
initial split-profile stress run (§15, 600 s cap) established the
partial-timeout baseline; the scoped single-language completion supplement
(§16, 1800 s timeout, Hybrid) completed `sample_g`, `sample_e`, and
reserve `sample_a` (historically surfacing the CER finding resolved by the
Caption Identity Gate); and the bilingual completion supplement (§17, 1800 s
timeout, Architecture B + DirectML product path) completed `sample_h`,
`sample_f`, and `sample_c` at 180/180 s coverage, 2.71× / 3.66× / 4.16×
realtime, 31/31 point recall, and 0/0 multilingual missing/wrong assignment
errors. Per formal human adjudication, Stage ⑤ is CLOSED. At the time
Stage ⑤ closed on 2026-09-03, Milestone 11 remained incomplete pending
Stage ⑥ Full Regression and Stage ⑦ Formal Human QA. Milestone 11
subsequently CLOSED on 2026-09-04 with Release Acceptance REJECTED BY
HUMAN ADJUDICATION; the product is now queued for Milestone 12
corrective rework. See `PROJECT_STATUS.md` and `ROADMAP.md` §18/§19 for
the current lifecycle truth.

| Step | State |
|---|---|
| ⑤-A Corpus selection | **CLOSED** — accepted at the human gate; the corpus below is frozen |
| ⑤-B Evaluation preparation | **CLOSED** — five ROI proposals approved unchanged (§6); all 44 ground-truth candidates confirmed with no corrections (§7, §9) |
| ⑤-C Representative evaluation | **CLOSED by Human Adjudication (2026-09-03)** — all five frozen windows completed 180/180 s. The stress run (§15, 600 s) and single-language supplement (§16, 1800 s Hybrid) are preserved as historical evidence; the bilingual supplement (§17, Architecture B + DirectML) completed `sample_h`/`sample_f`/`sample_c` at 100% coverage, ≤5× realtime, and 100% point recall. |

**Frozen corpus (⑤-A):** `sample_g` 90–270 s, `sample_e` 150–330 s,
`sample_h` 900–1080 s, `sample_f` 560–740 s, `sample_c` 480–660 s.

**Not done here, deliberately:** no ad-hoc OCR or temporal pipeline change, no
reopening of Beta-S / Auto-ROI research, no retuning of the 0.300
threshold, and no promotion of the Experimental Hybrid profile. Stage ⑤
evaluation and closure itself did not modify product code in `src/` —
all evaluation runs and artifacts live in `benchmarks/`, docs, or untracked
private corpus files. Product code modifications were strictly performed by
formal corrective gates triggered by Stage ⑤ findings (the Caption Identity
Corrective Gate in `875fb04`, P2/P3/P4B DirectML performance adapters in
`178038f`, and the mixed-script clustering veto in `075ac4b`).

**Privacy:** the corpus is untracked (`private_samples/` is in
`.gitignore`) and stays that way. This document describes the samples by
structural property only — resolution, caption layout, cadence — and
deliberately does not name the speakers, channels, publications or brands
that appear in them.

---

## 1. Inventory (measured, read-only)

Container and stream facts come from PyAV. All eight are H.264,
1920×1080, 30 fps, with no embedded subtitle stream — every caption is
burned in.

| Sample | Duration | Caption language | Layers | Background | Notable structure |
|---|---|---|---|---|---|
| `sample_a` | 7.2 min | Chinese only | 1 line | static studio | clean bottom caption bar; occasional screenshot/chart clutter |
| `sample_b` | 16.2 min | Chinese + English | 2 lines | static studio | plus large centred stylized pull-quote overlays, alternating dark/light |
| `sample_c` | 12.0 min | Chinese + English | 2 lines | static studio | caption **position and format vary**: full-screen title cards, a boxed paragraph held ~24 s |
| `sample_d` | 3.5 min | English + Chinese | 2 lines | static, two speakers | the "typical bilingual" baseline |
| `sample_e` | 12.4 min | **Chinese only** | 1 line | studio ↔ full-screen screen-share | dense spreadsheet screen-shares put **hundreds of non-caption text rows** in frame, some reaching into the caption band; one dark b-roll cut |
| `sample_f` | 17.4 min | English (yellow, top) + Chinese (white, below) | 2 lines, wraps to 3 | **alternates** talking-head ↔ outdoor b-roll inside a single window | fastest cadence measured; long English lines wrap |
| `sample_g` | 8.5 min | **English only** | 1 ↔ 2 lines | **handheld walking outdoors**, bright sky and snow | thin serif captions with **no dark rim or plate**, so contrast collapses against the sky; large stylized overlay cards sit above the caption band |
| `sample_h` | 25.5 min | Chinese (bright) + English (dim grey) | 2 lines, wraps to 3 | static studio, dark | a **permanently fixed footer strip** — speaker label, channel wordmark, logo lockup, rule — that never changes for 25 minutes |

`sample_a`–`sample_d` initially carried M10 point-sample ground truth in
the corpus manifest (10–20 verified instants each). Stage ⑤-B established
and confirmed point-sample ground truth for `sample_e`–`sample_h` (all 44
candidates confirmed at the human gate with no corrections, yielding 72
point-sample cues across 52 verified instants: `g` 11, `e` 10, `h` 20,
`f` 21, plus `c` 20 inherited from M10, and 2 verified negative points).

## 2. Caption-band dynamics (measured, read-only)

A pixel-level profile of the bottom band (y ∈ [0.68, 1.00], sampled at
5 Hz over the window named): a bright-core-with-local-contrast mask, then
band occupancy and frame-to-frame mask divergence. **This is a corpus
characterisation heuristic, not OCR** — it shares no threshold, no policy
and no code with the product pipeline, and its numbers are comparative,
not ground truth.

| Sample | Window profiled | Text present | Blank gaps | Change events / min | Band ink |
|---|---|---|---|---|---|
| `sample_a` | 15–195 s | 100% | 0 | 42.4 | 4.16% |
| `sample_b` | 270–450 s | 99% | 3 | 34.4 | 7.22% |
| `sample_c` | 480–660 s | 100% | 4 | 26.3 | 5.96% |
| `sample_d` | 20–200 s | 100% | 0 | 33.7 | 6.96% |
| `sample_e` | 150–330 s | 100% | 0 | 26.7 | 6.48% |
| `sample_f` | 560–740 s | 98% | 15 | **49.0** | 3.30% |
| `sample_g` | 90–270 s | 99% | 1 | **13.7** | **1.88%** |
| `sample_h` | 900–1080 s | 98% | 7 | 40.3 | 3.31% |

Reading the two extremes: `sample_g` is the **faintest and slowest**
(thin unplated serif, long captions held several seconds) and `sample_f`
the **fastest** (a caption change roughly every 1.2 s, with real blank
gaps between them). The high band ink on `b`, `c` and `e` is not caption
weight — it is overlay and screen-share text intruding into the band,
which is exactly the condition those samples exist to exercise.

---

## 3. Candidate matrix

Five candidate windows, each 3 minutes, inside the 2–5 minute target.

| # | Candidate | Window | Why it is in | Risk it covers |
|---|---|---|---|---|
| 1 | `sample_g` | **90–270 s** | The only **English-only** source in the corpus, and the only handheld one. Captions are thin serif with no plate over bright sky and snow — the lowest band ink measured (1.88%). The window contains stylized overlay cards above the caption band and both 1-line and 2-line captions. | English-only reconstruction; low-contrast detectability; camera motion; overlay text outside the ROI; 1↔2 line morphology |
| 2 | `sample_e` | **150–330 s** | The only Chinese-only source with **competing on-screen text**. The window spans a dense spreadsheet screen-share, a dark b-roll cut and clean talking-head, so the background type changes three times while the caption style does not. | Chinese-only single-line; false positives from non-caption text; ROI discipline; background switching mid-run |
| 3 | `sample_h` | **900–1080 s** | Bilingual with an **unchanging footer strip** for the whole 25 minutes, and a dim grey second language on a dark set. Fast cadence (40 changes/min). Taken from deep inside a long file, so processing-range resolution against a 25-minute timeline is exercised too. | **Duplicate user-facing Cues from a static overlay observed on every frame**; second-language low contrast; non-zero processing-range offset on a long source |
| 4 | `sample_f` | **560–740 s** | The fastest cadence measured (49/min) with **15 genuine blank gaps** — the only window that is dense *and* intermittent. The background alternates talking-head ↔ outdoor b-roll inside the window, and long English lines wrap from 2 lines to 3. | Fast caption switching; cue boundary and merge behaviour at speed; sparse↔dense transitions; dynamic background; long-caption wrap |
| 5 | `sample_c` | **480–660 s** | Retained from M10. The only sample where the caption **position and format change**, not just the text: full-screen title cards interleaved with the bottom bar, and a boxed statistic paragraph held ~24 s. Carries 20 verified ground-truth instants, giving one window with M10 continuity. | Caption position/format change within one run; the static long-hold extreme; regression comparability against M10 |

### Reserves, and why they are not in the recommended corpus

| Sample | Disposition |
|---|---|
| `sample_a` | **Reserve — clean baseline.** Chinese-only clean studio; covered on language and layout by `sample_e`, which adds a stressor `a` lacks. Worth keeping as the easy-case control if the corpus fails broadly and a sanity baseline is needed — it has ground truth and an existing reconstructed SRT. |
| `sample_b` | **Out.** Bilingual plus stylized pull-quote overlays. Its distinguishing risk (stylized overlay near captions) is covered by `sample_g`, and its bilingual two-line layout by `sample_f` and `sample_h`. |
| `sample_d` | **Out.** The "typical bilingual" case, fully contained by `sample_f` and `sample_h`, both of which add a stressor `d` does not have. |

### Coverage check

| Axis | Covered by |
|---|---|
| English-only | `sample_g` |
| Chinese-only | `sample_e` |
| Bilingual | `sample_f`, `sample_h`, `sample_c` |
| Fast caption switching | `sample_f` (49/min), `sample_h` (40/min) |
| Slow / long-held captions | `sample_g` (13.7/min), `sample_c` (~24 s hold) |
| 1 ↔ 2 line change | `sample_g`; `sample_f` and `sample_h` also 2↔3 |
| Short captions | `sample_e` |
| Long captions | `sample_g`, `sample_c` |
| Static background | `sample_h`, `sample_c`, `sample_e` (in part) |
| Dynamic background | `sample_g` (handheld), `sample_f` (b-roll cuts) |
| Sparse / intermittent captions | `sample_f` (15 gaps), `sample_h` (7 gaps) |
| Dense continuous captions | `sample_e`, `sample_c` |
| Competing non-caption text | `sample_e` (screen-share), `sample_g` (overlay cards), `sample_c` (title cards), `sample_h` (fixed footer) |
| Low contrast | `sample_g` (unplated on sky), `sample_h` (dim second line) |

No axis is uncovered, and no two candidates are the primary carrier of
the same pair of axes.

## 4. Recommended corpus

**All five**, in this order — `sample_g`, `sample_e`, `sample_h`,
`sample_f`, `sample_c`. If the run budget forces a cut, drop from the
bottom: `sample_c` first (M10 continuity is the least novel of the five),
then `sample_f` (its cadence axis is partly held by `sample_h`). The top
three are not interchangeable — each is the sole carrier of a language or
of a failure mode.

Total material: 15 minutes of video, 5 windows, 5 distinct sources.

## 5. Open items carried out of ⑤-A

- Ground truth did not exist for the `sample_e` / `sample_f` /
  `sample_g` / `sample_h` windows → addressed as **candidate** worksheets
  in §7; still unconfirmed.
- Per-window ROI had not been proposed → §6.
- The corpus must be run through the hardened harness
  (`benchmarks/_job_harness.py`). The M10 crash condition
  (`docs/m10_private_corpus_incident.md`) has not been re-verified
  against these specific windows.

---

# ⑤-B Evaluation Preparation

## 6. ROI proposals

### The contract these obey

`glyphcue.application.hybrid_evidence_job` states V1's ROI contract
plainly: the ROI is **a coarse, user-drawn search envelope**, uniform
padding and software-proposed ROIs were both tried and rejected, and the
UI asks the user to leave margin for wider and taller captions instead.
Its measured residual risk sets the priority: a caption the ROI does not
cover is detected on **zero** frames and produces no cue at all — an
unrecoverable loss — whereas a distractor the ROI does cover produces
extra observations a reviewer can see and reject. **So where the two
conflict, these proposals favour covering the caption.**

Each proposal is a `glyphcue.domain.roi.ROI`, validated against it, and
each value is exact at the ROI spin boxes' 3 decimals, so nothing is
quantized on the way in.

### Proposals

| Window | ROI `(x, y, width, height)` | ROI covers y | Caption block measured at | Margin above / below |
|---|---|---|---|---|
| `sample_g` 90–270 s | **(0.05, 0.80, 0.90, 0.20)** | 0.80–1.00 | 0.860–0.967 | 0.060 / 0.033 |
| `sample_e` 150–330 s | **(0.05, 0.85, 0.90, 0.15)** | 0.85–1.00 | 0.900–0.967 | 0.050 / 0.033 |
| `sample_h` 900–1080 s | **(0.05, 0.73, 0.90, 0.19)** | 0.73–0.92 | 0.780–0.907 | 0.050 / 0.013 |
| `sample_f` 560–740 s | **(0.05, 0.76, 0.90, 0.24)** | 0.76–1.00 | 0.817–0.967 | 0.057 / 0.033 |
| `sample_c` 480–660 s | **(0.05, 0.50, 0.90, 0.47)** — inherited from M10 unchanged | 0.50–0.97 | 0.767–0.933 bottom bar, plus title cards mid-frame | wide by design |

All five keep M10's horizontal framing (x 0.05–0.95). Captions in these
windows are centred and the widest measured lines stay well inside it;
the residual-risk note's failure case was a caption **81% of frame
width**, which 0.90 still covers.

### Verification (sampled at 2.5 Hz across each full window, 451 frames each)

| Window | Caption rows carry ink | Known distractor | Distractor inside the ROI |
|---|---|---|---|
| `sample_g` | 451/451 (100%) | 3 stylized-card episodes (≈148.0–150.4 s, ≈230.0–232.4 s, ≈258.0–263.2 s), 28/451 frames | **21/451 frames (4.7%)** — see below |
| `sample_e` | 451/451 (100%) | screen-share table text | rows 0.850–0.895 carry table text on **399/451 frames (88%)** — admitted deliberately |
| `sample_h` | 450/451 (100%) | fixed footer strip, rows 0.930–0.980, present on **451/451 frames (100%)** | **0/451 (0%)** — fully excluded; and no ink at all in the 2.5% just below the ROI bottom, so nothing is clipped there either |
| `sample_f` | 451/451 (100%) | none fixed; b-roll screen recordings carry their own text at caption height | ink above the ROI top on 31/451 (6.9%) |
| `sample_c` | 451/451 (100%) | title cards / boxed paragraph — inside the ROI **on purpose** | n/a |

### Per-window notes

**`sample_g` — the overlay cards cannot be fully excluded by a rectangle.**
Measured at the ≈149 s card: the card's big word descends to **y ≈ 0.85**,
while the caption's own top line begins at **y ≈ 0.86**. There is a 0.01
gap between them. Any ROI top that excludes the card leaves *no* margin
for a taller caption, which the contract explicitly asks for. The
proposal therefore takes y = 0.80: it fully excludes the ≈230 s episode
and the mid-frame cards (the numbered list card ends at y ≈ 0.712), and
admits the bottom sliver of the other two episodes on 21 of 451 sampled
frames (4.7% of the window, roughly 8 s of 180 s). Expect a handful of
reviewable extra observations there rather than a perfectly clean run.
*Alternative, if the human gate prefers exclusion over margin:*
`(0.05, 0.855, 0.90, 0.145)` — excludes all three card episodes, but
clips any caption taller than the two lines seen so far.

**`sample_e` — the ROI top is a deliberate compromise.** Screen-share
table rows reach down to ≈0.895, one line above the caption at 0.900.
A top of 0.85 keeps roughly one extra caption line of margin and accepts
table text in rows 0.850–0.895 on 88% of frames. Tightening to 0.89 would
buy a cleaner run at the cost of all vertical margin.
*Alternative, if the gate prefers coverage over cleanliness:*
`(0.05, 0.80, 0.90, 0.20)`.

**`sample_h` — the clean case.** The caption block (0.780–0.907) and the
fixed footer (0.930–0.980) are separated by an empty 0.023 band, so one
rectangle both covers the captions with margin and excludes the footer
completely. This is the ROI the duplicate-cue risk is being tested
against, and the measurement above says the footer is 100% present and
0% inside the ROI. The 12.4% of frames with ink just above the ROI top is
set lighting, not caption — it sits above the measured caption block.
Caveat: the margin below the caption block is only 0.013, so if a caption
ever wraps lower than anything seen in this window it would clip. This is
the ROI most worth eyeballing in the app before the run.

**`sample_f` — no fixed overlay to exclude.** The distractors here are
b-roll screen recordings whose own UI text sits at the caption's own
height, so no ROI can separate them. That is the risk this window exists
to exercise, not something to design around.

**`sample_c` — inherited, not re-proposed.** This is the one window with
verified M10 ground truth. Changing its ROI would break comparability
with M10's numbers, and its defining risk (caption position and format
change) needs the wide band. Kept exactly as M10 had it, with its known
trade-off: it admits mid-frame title-card and pull-quote text by design.

## 7. Ground-truth candidate worksheets (`e` / `f` / `g` / `h`)

**These are candidates, not ground truth.** Every worksheet row has an
empty `text`, an empty `language`, a null `confirmed_line_count`, a null
`timing_correct` and `confirmed: false`. Nothing here claims a verified
transcription, and no OCR was run to produce them.

Where they live (untracked, alongside M10's own manifest):

```
private_samples/m10_video_corpus/export docu/sample_<e|f|g|h>_gt_worksheet.json
private_samples/m10_video_corpus/export docu/sample_<e|f|g|h>_gt_evidence.png
```

**Method.** The window is sampled at 5 Hz inside the proposed ROI band; a
bright-core-with-local-contrast mask segments it into caption *states*
(a new state whenever the mask diverges by more than 45% from the
previous one, or after a blank frame). States shorter than 0.6 s are
discarded as transition frames rather than captions. Eleven states are
then chosen per window — one for each risk category, the rest spread
evenly — and a labelled frame crop is exported for each so the reviewer
can read the caption and fill the row in. No product code path, threshold
or policy is involved.

**What each worksheet proposes.**

| Window | States found | Long enough to propose | Candidates |
|---|---|---|---|
| `sample_e` 150–330 s | 94 | 88 | 11 |
| `sample_f` 560–740 s | 160 | 77 | 11 |
| `sample_g` 90–270 s | 44 | 44 | 11 |
| `sample_h` 900–1080 s | 129 | 86 | 11 |

**Risk coverage carried by the selection reasons** — every row states
which one it is, in `selected_because`:

| Risk | Selection reason used |
|---|---|
| Ordinary caption | evenly spread across the window |
| Short caption / fast transition | shortest state ≥ 0.6 s |
| Long caption / static hold | longest-held state — `sample_e` #10 runs 302.6–328.4 s (25.8 s); `sample_g` #7 runs 9.2 s |
| 1 ↔ 2/3 line change | the most-lines state, plus a state with fewer lines than the window median |
| Blank-gap boundary | first and last states adjacent to a no-text frame (`sample_f`, `sample_h`) |
| Low contrast | lowest band ink in the window |
| Competing screen text | highest band ink in the window — in `sample_e` and `sample_f` these land on the screen-share and b-roll passages |

**What the reviewer does per row:** read the numbered tile in the evidence
sheet, type the caption `text` and its `language`, correct
`observed_start_seconds` / `observed_end_seconds` if the heuristic cut the
state wrongly (`timing_correct`), set `confirmed_line_count`, then set
`confirmed: true`. `observed_line_count` is a rough row-run estimate and
is expected to be wrong sometimes — it is a hint, not a claim.

**`sample_c` is untouched**: it keeps its 20 verified M10 ground-truth
instants from the corpus manifest. No new worksheet was generated for it,
and no manual work was duplicated.

## 8. What must be confirmed before ⑤-C starts

*Disposition, after the ⑤-B gate: items 1 and 2 are closed (§9), and items 4, 5 and 6 are closed (§10, §12). Item 3 — which profile the run uses — was answered (Experimental Hybrid) and that answer is what §13 now blocks on.*

**Human gate:**

1. **The five ROI proposals**, and specifically the two trade-offs called
   out above — `sample_g` (accept 4.7% card intrusion, or switch to the
   tighter alternative and lose caption margin) and `sample_e` (accept
   88% table intrusion, or switch to the wider alternative). Drawing them
   once in the app and eyeballing them against a few frames is the
   cheapest confirmation; `sample_h`'s narrow 0.013 bottom margin is the
   one most worth checking.
2. **The ground-truth worksheets**, filled in and set `confirmed: true`,
   or an explicit decision to report `e` / `f` / `g` / `h` qualitatively
   instead. `EVALUATION_REPORT.md` must say which was chosen.
3. **Which profile the run uses.** Nothing in stage ⑤ has promoted the
   Experimental Hybrid profile; if the evaluation is meant to run it,
   that is a decision, not a default.

**Mechanical prerequisites, not done here deliberately:**

4. `benchmarks/private_video_corpus/run_evaluation.py` reads its manifest
   from `private_samples/m10_video_corpus/manifest.json`, but the corpus
   manifest currently sits at
   `private_samples/m10_video_corpus/export docu/manifest.json`. As it
   stands the harness would not find it. Left alone rather than fixed
   blind, because the fix depends on item 5.
5. The manifest needs four new entries for `sample_e` / `f` / `g` / `h`
   in the existing `glyphcue.evaluation.corpus` schema — `id`,
   `video_path`, `segment_start_seconds` / `segment_end_seconds` from the
   frozen windows, `languages`, `visibility: private`, and the confirmed
   `ground_truth_cues`. Those ids are also the keys `_ROI_BY_ENTRY_ID` in
   `run_evaluation.py` needs, so the naming has to be settled before
   either file is edited.
6. The M10 crash condition (`docs/m10_private_corpus_incident.md`) has
   not been re-verified against these five specific windows on the
   hardened harness.

# ⑤-C Evaluation Preflight

## 9. Ground truth — confirmed

The ⑤-B human gate confirmed all 44 candidate points (11 × 4) with no
corrections. The untracked worksheets are now filled in and marked
`CONFIRMED -- human-verified point samples`.

| Window | Candidates | Negative points | Verified instants | Ground-truth cues emitted |
|---|---|---|---|---|
| `sample_g` 90–270 s | 11 | 0 | 11 | 11 (`en`) |
| `sample_e` 150–330 s | 11 | **1** (#5) | 10 | 10 (`zh`) |
| `sample_h` 900–1080 s | 11 | **1** (#9) | 10 | 20 (`zh` + `en`) |
| `sample_f` 560–740 s | 11 | 0 | 11 | 21 (`en` + `zh`, one instant `en`-only) |
| `sample_c` 480–660 s | inherited from M10 | 0 | 10 | 20 (`en` + `zh`) |

Rules applied, exactly as the gate specified:

- **Verbatim.** Each point records the burned-in caption text as it
  appears on screen. No grammar correction, no punctuation
  normalisation, no rewriting — including where the source captions are
  themselves ungrammatical or uncapitalised.
- **`sample_e` #5 and `sample_h` #9 are negative points.** They are
  marked `subtitle_present: false` in the worksheets and deliberately
  emit **no** ground-truth cue: a point-recall metric has no meaning for
  an instant with nothing to recall. They remain in the worksheets as
  evidence, and are the natural basis for a later false-positive check.
- **`sample_g` #4's large "stylized overlay" text is excluded.** Only the
  burned-in caption beneath it is ground truth. This is the same overlay
  the ROI cannot fully exclude (§6), so the distinction is recorded on
  the row itself.
- **`sample_c` is untouched**, still carrying its 20 verified M10
  instants.

One point could not be fully transcribed and is recorded as such rather
than guessed: **`sample_f` #7's Chinese layer is present but illegible**
in the evidence frame — a white caption over a white full-screen b-roll
screenshot. Its English layer is confirmed and emitted; no `zh` cue is
emitted for that instant. That is why `sample_f` has 21 cues across 11
instants rather than 22. This is itself a finding about the window, and
is the one ground-truth item that would change if the gate wants to
re-read that frame by hand.

## 10. Manifest and harness configuration

**Manifest path inconsistency — resolved.**
`benchmarks/private_video_corpus/run_evaluation.py` reads
`private_samples/m10_video_corpus/manifest.json`; that file now exists
and is the canonical corpus manifest, holding exactly the five frozen
entries. The historical M10 export at
`private_samples/m10_video_corpus/export docu/manifest.json` was left
untouched as the M10 record; no code reads it. Both stay untracked.

**Entry ids** (these are simultaneously the manifest keys and the
`_ROI_BY_ENTRY_ID` keys — the preflight fails if they ever disagree):

| Entry id | Window | Languages | ROI `(x, y, w, h)` |
|---|---|---|---|
| `private-g-english-handheld` | 90–270 s | `en` | (0.05, 0.80, 0.90, 0.20) |
| `private-e-chinese-screenshare` | 150–330 s | `zh` | (0.05, 0.85, 0.90, 0.15) |
| `private-h-bilingual-fixed-overlay` | 900–1080 s | `zh`, `en` | (0.05, 0.73, 0.90, 0.19) |
| `private-f-bilingual-fast-broll` | 560–740 s | `en`, `zh` | (0.05, 0.76, 0.90, 0.24) |
| `private-c-difficult-mixed-format` | 480–660 s | `en`, `zh` | (0.05, 0.50, 0.90, 0.47) |

The ROI values are exactly the ⑤-B proposals, unchanged.

**Profile.** `EVALUATION_PROFILE` is a named module constant, frozen at
`EvidenceJobProfile.EXPERIMENTAL_HYBRID`. It is named rather than
defaulted so a results file can be traced to the pipeline that produced
it — the same reason `build_evidence_job_for_profile` makes its callers
name a profile. A hybrid run now constructs a real
`PaddleOcrTextDetector` per entry and shuts it down before the next
entry builds its own.

**New harness entry points** (both refuse to do anything if the private
corpus is absent, so a fresh clone and CI are unaffected):

- `--preflight` — validates the corpus, ROI table, ranges, ground-truth
  placement and profile compatibility. Reports **every** problem at once
  and runs nothing. `run()` now calls it first and will not start a job
  unless it passes.
- `--crash-check` — re-verifies the M10 incident's failure mode against
  the real windows using a stub recognizer, so it cannot become an
  accidental evaluation run.

## 11. Preflight result

Structural checks — all five entries **PASS**:

| Check | Result |
|---|---|
| Manifest loads under `glyphcue.evaluation.corpus` schema | 5/5 |
| Video file present | 5/5 |
| Entry id has an ROI in `_ROI_BY_ENTRY_ID` | 5/5 |
| `ProcessingRange.resolve()` accepts the window against the real probed duration | 5/5 |
| Every verified ground-truth instant falls inside its window | 5/5 (72 cues, 52 instants) |

Profile compatibility — **2 of 5 entries runnable under the frozen
profile**, and preflight refuses the run because of it. See §13.

## 12. M10 crash condition — re-verified, does NOT reproduce

The M10 incident was an orchestration failure, not an OCR failure: the
old `_run_job` timeout path called only `loop.quit()`, never
`job.request_cancel()`, so an overrunning job kept running on an orphaned
thread while the loop started the next entry — turning a sequential run
into unbounded concurrency. A second, smaller bug left a SQLite
connection open, so the temporary directory could not be deleted and the
crash surfaced as `PermissionError`.

`--crash-check` reproduces the *conditions* on all five real windows:
each entry's real job is built on its real window and ROI, given a
deliberately tiny 1.0 s timeout so it is guaranteed to overrun, and the
recognizer is stubbed so no OCR runs. Each entry is checked through the
job type it would really use — the hybrid job where the frozen profile
supports the entry, the production job where it does not.

| Entry | Job profile exercised | Terminal state | Worker thread left alive |
|---|---|---|---|
| `private-g-english-handheld` | experimental_hybrid | `cancelled` | no |
| `private-e-chinese-screenshare` | experimental_hybrid | `cancelled` | no |
| `private-h-bilingual-fixed-overlay` | production_trigger | `cancelled` | no |
| `private-f-bilingual-fast-broll` | production_trigger | `cancelled` | no |
| `private-c-difficult-mixed-format` | production_trigger | `cancelled` | no |

- Every job reached a terminal state, and every one of them `cancelled`
  — overran, was asked to stop, and stopped. (A `failed` state would also
  be "terminal", so the check reports both, and a failure invalidates its
  own verdict rather than passing quietly.)
- **No worker thread was left alive**, which is the orphaned-thread
  condition itself.
- The temporary directory deleted cleanly on Windows — the secondary M10
  bug's exact symptom would have been a `PermissionError` here.
- Live progress was reported throughout (7–161 updates per entry); the
  M10 incident's compounding "no way to see it stalling" gap is visibly
  closed.

No harness defect was found, so nothing was fixed and no new regression
test was added. `tests/benchmarks/test_job_harness.py` already pins the
harder case — a job that refuses to cooperate must abort the whole run
rather than let the next entry start.

## 13. Blocker: the frozen profile cannot run the three bilingual windows — RESOLVED (Option A approved)

`EXPERIMENTAL_HYBRID` is single-language **by construction**:
`build_hybrid_ocr_evidence_job` takes one `OcrEngine`, not a per-language
mapping, and `path_a_media_pane` already refuses a multilingual Hybrid
run in the UI for the same reason. Three of the five frozen windows —
`sample_h`, `sample_f`, `sample_c` — are bilingual.

Three options were set out, each costing something different:

| Option | What it means | Cost |
|---|---|---|
| **A. Split profile** — **approved at the ⑤-C human gate** | Hybrid on `sample_g` + `sample_e`; production trigger on `sample_h`, `sample_f`, `sample_c`. | Cross-window comparison mixes two pipelines. Every metric stays valid *within* a profile; nothing is merged across them. |
| B. Hybrid everywhere, one language per window | Pick a single language for each bilingual window and run Hybrid on it. | The other layer's confirmed ground truth must be dropped, and multilingual layer-assignment metrics are lost on 3 of 5 windows. Not chosen. |
| C. Hybrid twice per bilingual window, merged | One hybrid run per language, observations merged before multilingual reconstruction. | Not a small change, and not obviously sound — `build_multilingual_ocr_evidence_job` deliberately makes the OCR-trigger decision once per frame, shared across languages, which two independent hybrid runs would not preserve. Not chosen. |

**Implementation.** `_PROFILE_BY_ENTRY_ID` in
`benchmarks/private_video_corpus/run_evaluation.py` assigns a profile to
every entry explicitly:

| Entry id | Profile |
|---|---|
| `private-g-english-handheld` | `experimental_hybrid` |
| `private-e-chinese-screenshare` | `experimental_hybrid` |
| `private-h-bilingual-fixed-overlay` | `production_trigger` |
| `private-f-bilingual-fast-broll` | `production_trigger` |
| `private-c-difficult-mixed-format` | `production_trigger` |

`preflight()` requires every manifest entry to resolve a profile from
this table and refuses a multilingual entry assigned Hybrid; both job
runners (`_run_single_language_job`, `_run_multilingual_job`) resolve and
return the actual profile they ran under, and `_evaluate_entry` records
it on every result row (`"profile": "..."`). `_summarize_by_profile`
groups every aggregate strictly by that field — mean recall, mean CER,
mean realtime ratio, cue and observation totals are each computed only
within one profile's rows, never across both. Re-run under this wiring:
preflight and `--crash-check` both confirm **5/5 windows runnable**, with
`profiles_used: ["experimental_hybrid", "production_trigger"]`.

## 14. The run command

```
python -m benchmarks.private_video_corpus.run_evaluation --preflight
python -m benchmarks.private_video_corpus.run_evaluation --crash-check
python -m benchmarks.private_video_corpus.run_evaluation
```

Requirements: the `[ocr]` extra (present locally: `paddleocr` and
`paddle` both import) and the private corpus. Results are written to
`private_samples/m10_video_corpus/evaluation_results.json` — untracked,
and only ever summarised into `EVALUATION_REPORT.md` in anonymised form.

Standing cost warning: the per-entry job timeout is 600 s and M10's own
numbers on this corpus were far slower than realtime
(`docs/m10_performance_diagnosis.md`). A window that overruns is
cancelled cleanly — verified in §12 — but it will then have covered only
part of its 180 s, and that partial coverage is reported honestly
(`completion: "partial_timeout"` on that entry) rather than retried until
it looks better.

## 15. Real run — results and adjudication

**Executed:** `python -m benchmarks.private_video_corpus.run_evaluation`,
2026-09-02. Exit code 0, no exception, no Python traceback anywhere in
the run log. Results written to the untracked
`private_samples/m10_video_corpus/evaluation_results.json`; the numbers
below are that file's content, anonymised (no caption text, no frame
content, no timestamps beyond the frozen windows already named in this
document).

**Headline finding, stated first because it governs how to read
everything below: none of the five windows completed.** Every entry hit
its 600 s per-entry timeout, was cancelled cleanly (consistent with §12's
crash-check), and stopped with only part of its 180 s window processed.
This is the exact real-world performance cost `docs/m10_performance_diagnosis.md`
already flagged, now reproduced on all five real windows rather than
inferred from confounded M10 evidence or a synthetic fixture. **It is
reported as observed, not retried or tuned to look better** — see item 1
under Human Adjudication.

### Per-window result

| Entry | Profile | Completion | Window coverage | Point recall | Mean CER (matched points only) | Cues / Observations | Realtime ratio |
|---|---|---|---|---|---|---|---|
| `sample_g` (English-only, handheld) | Hybrid | partial_timeout | 90.4 / 180 s (50.2%) | 5/11 (45.5%) | en 0.017 | 17 / 59 | 6.8× |
| `sample_e` (Chinese-only, screen-share) | Hybrid | partial_timeout | 109.6 / 180 s (60.9%) | 6/10 (60.0%) | zh 0.492 | 58 / 64 | 5.6× |
| `sample_h` (bilingual, fixed footer) | Production | partial_timeout | 4.8 / 180 s (2.7%) | 1/10 (10.0%) | zh 0.0, en 0.145 | 5 / 114 | 128.6× |
| `sample_f` (bilingual, fast cadence) | Production | partial_timeout | 3.9 / 180 s (2.2%) | 1/11 (9.1%) | en 0.0, zh 1.0 | 8 / 104 | 158.9× |
| `sample_c` (bilingual, position/format change) | Production | partial_timeout | 6.3 / 180 s (3.5%) | 1/10 (10.0%) | en 0.32, zh 0.0 | 4 / 62 | 98.8× |

Total wall clock across all five: 3096.6 s (51.6 min). Every job's own
timeout (600 s) accounts for almost all of that — the small remainder is
model construction, decode setup and the cancellation grace period.

**"Mean CER (matched points only)" is exactly that** — computed only over
the verified instants a real Cue actually covered, per this harness's
stated scope (module docstring, and the M10 methodology it inherits): it
says nothing about the 45–90% of instants no Cue reached at all under
this run's timeout. A single matched point drives most of these numbers
(`sample_h`, `sample_f`, `sample_c` each matched exactly one), so none of
the Production-profile CER figures should be read as a stable accuracy
estimate — they are one data point each.

**`sample_f`'s zh CER = 1.0 is a missing layer, not a wrong transcription.**
`multilingual_missing_layer_count: 1` on that entry confirms it: the one
matched instant produced an English Cue with no Chinese layer at all, so
`character_error_rate` against an empty string reads as total error. This
is unrelated to the illegible-frame candidate (#7) from the confirmed
ground truth, which was deliberately given no zh ground-truth cue in the
first place (§9) — the matched instant here is a different, earlier one,
reachable only because `sample_f`'s window coverage stopped at 3.9 s.

### Correctness and performance, by profile — never merged

Per the instruction this run was scoped under, the two profiles are
reported strictly separately. No number below averages a Hybrid entry
with a Production entry.

| | Hybrid (`sample_g`, `sample_e`) | Production (`sample_h`, `sample_f`, `sample_c`) |
|---|---|---|
| Mean point recall | **52.7%** | **9.7%** |
| Mean CER (matched points only) | 0.255 | 0.244 |
| Mean realtime ratio | **6.2×** | **128.8×** |
| Total user-facing cues | 75 | 17 |
| Total observations | 123 | 280 |
| OCR (recognition) calls / media-second | g: 0.37/s, e: 0.54/s | h: 7.9/s, f: 9.2/s, c: 3.2/s |
| Detector calls (Hybrid only) | g: 161 (163.6 s), e: 127 (129.2 s) | n/a (`detector_calls: 0` by construction) |

**The recall and realtime-ratio gap is large and consistent across both
entries in each group** — not a one-off. On these specific real,
non-static, real-world windows, `EXPERIMENTAL_HYBRID`'s detector-anchored
scheduling issued OCR recognition calls at roughly 1/15–1/25th the
density `PRODUCTION_TRIGGER`'s `ChangeTriggeredOcrPolicy` did, and
finished 6–20× more of its window before hitting the same 600 s ceiling.
This is exactly the mechanism `docs/m10_performance_diagnosis.md`
hypothesised (real, non-static backgrounds over-trigger the change-detection
threshold) — it is now measured directly on real background footage
rather than inferred from M10's contention-confounded numbers, and the
gap this run measured is larger than anything in that document.

**What this finding is NOT:** a controlled Hybrid-vs-Production
benchmark. The two groups are also two different kinds of content — the
two Hybrid windows are the corpus' two single-language, single-speaker
entries; the three Production windows are its three bilingual,
visually busier entries (screen-shares, position changes, a fixed
overlay). Content and profile are confounded here by construction (Hybrid
cannot run the bilingual windows at all — that's §13's whole reason for
existing), so this run cannot separate "Hybrid is faster" from "these two
windows happen to be easier to process quickly." **No conclusion is drawn
from this about promoting Experimental Hybrid to default Production, and
none should be** — that question needs its own controlled evidence, which
is explicitly out of scope for this run.

### Observed failures

None. Every job reached `cancelled` cleanly — no exception, no
`PermissionError`, no orphaned worker thread (consistent with §12's
crash-check), no Python traceback anywhere in the run log.

### Human Adjudication needed

1. **The 600 s per-entry timeout leaves every window mostly unprocessed.**
   Raising it is a harness parameter, not an OCR/temporal algorithm
   change and not a 0.300 retune — but it was **not** changed
   unilaterally in this pass, per the explicit instruction not to
   re-tune and re-run for a better number. Whether to re-run with a
   longer timeout (and how long — Production's own numbers suggest it
   would need well over an hour per bilingual window to finish 180 s) is
   a call for the gate, not the harness.
2. **`sample_h`'s duplicate-cue risk (the reason it was chosen in ⑤-A) is
   inconclusive.** Only 2.7% of its window was processed, too little to
   say whether the fixed footer produced duplicate user-facing Cues or
   not. This specific window is the strongest candidate for a longer
   individual timeout if only one is extended.
3. **Whether the Hybrid/Production performance gap above is real signal
   or a content-confound artifact** needs a controlled follow-up (same
   content, both profiles) before it informs any roadmap decision — not
   attempted here, and explicitly not a basis for touching M11's
   Research Gate disposition on Experimental Hybrid.
4. **Whether these partial results are sufficient to fold into
   `EVALUATION_REPORT.md`** as this stage's contribution to ROADMAP §18
   acceptance gate 9, reported honestly as partial (exactly as M10's own
   evidence was), or whether the gate wants fuller coverage first.

**Stage ⑤ is NOT closed by this run.** Nothing above is a PASS/FAIL
verdict on the product; it is evidence, reported exactly as produced,
for the gate to read.


---

## 16. Completion supplement (2026-09-02 human gate) — results

**This section is additive to §15, not a replacement for it.** §15's
five-window stress run (`evaluation_results.json`) is unchanged and
untouched — every one of its five entries stays recorded exactly as
produced, `partial_timeout`, at the 600 s per-entry cap. This section
covers a separate, narrower run
(`evaluation_results_completion_supplement.json`, written by
`run_completion_supplement()`) that asks only: given more wall-clock
budget, do the two already-Hybrid-eligible stage 5 windows and the
pre-existing M10 clean-baseline reserve actually finish?

**Scope, exactly as approved:** `sample_g` and `sample_e` at their
unchanged ⑤-A/⑤-B window and ROI (loaded from the same
`manifest.json` used by the main run — byte-identical, not re-specified),
plus `sample_a` reusing M10's own window (15.0–192.0 s, 177 s — inside
the 2–5 minute contract), ROI and 10 verified ground-truth instants
verbatim, not a newly hand-picked segment. All three under
`EXPERIMENTAL_HYBRID` only. The one parameter changed from the main run
is the per-entry timeout: 1800 s instead of 600 s. Nothing under `src/`
was touched; `sample_h`, `sample_f` and `sample_c` were not re-attempted.

### Result: all three completed

| Entry | Window | Completion | Coverage | Point recall | Mean CER | Cues / Obs | Realtime ratio | Wall clock |
|---|---|---|---|---|---|---|---|---|
| `sample_g` (en, handheld) | 90–270 s | **completed** | 180/180 s (100%) | **11/11 (100%)** | en 0.163 | 37 / 110 | 7.2× | 1296.0 s |
| `sample_e` (zh, screen-share) | 150–330 s | **completed** | 180/180 s (100%) | **10/10 (100%)** | zh **1.166** | 89 / 215 | 7.7× | 1388.6 s |
| `sample_a` (zh, clean baseline, M10) | 15–192 s | **completed** | 177/177 s (100%) | **9/10 (90%)** | zh **1.679** | 92 / 635 | 10.1× | 1786.9 s |

Total wall clock: 4471.4 s (74.5 min). All three reached `succeeded`
(not a timeout cancellation) — the extra budget was sufficient this time,
and none of the three needed the full 1800 s.

### Reading these numbers correctly

**Recall is strong across the board** — once given enough time to finish
its window, Hybrid found a Cue covering 30 of the 31 verified instants
across all three entries. This is a real, positive result and stands
independent of the CER finding below.

**Mean CER is a serious, unresolved correctness finding, reported exactly
as measured — not smoothed over.** `sample_g`'s English CER (0.163) is in
a normal range. **Both Chinese-language entries measure CER above 1.0**
(`sample_e`: 1.166, `sample_a`: 1.679) — by definition (`character_error_rate`
= Levenshtein edit distance / reference length, unbounded above), this
means the reconstructed text at matched instants diverges from the
short, verified ground-truth line by *more* edits than the reference
itself contains — consistent with the recovered text being substantially
longer than, or substantially different in content from, the reference,
not merely containing a few wrong characters.

**A plausible mechanism exists but is explicitly NOT verified this
round, and no further investigation was done, per this run's scope:**
Hybrid performs "ONE recognition per state"
(`hybrid_evidence_job.py`'s own module docstring) — if the state-grouping
step merges a wider visual span than one caption's worth of text (a real
risk on `sample_a`'s dense-cadence source, where `sample_a` alone
produced 635 observations across only 92 Cues, a much higher
observations-per-Cue ratio than `sample_g` or `sample_e`), the single
recognized block could span content from more than one real caption,
making it much longer than any one verified instant's reference text.
This is a hypothesis, not a diagnosis — the underlying observation data
was not re-inspected to confirm it, per the instruction not to reopen
OCR/temporal research this round.

**What this does and does not affect:** it does not change point recall
(a Cue was still found covering the right timestamp) or the §15
Hybrid-vs-Production realtime-ratio finding (unaffected, both concern
timing/coverage, not recognized-text accuracy). It is a new, previously
unmeasured signal about Hybrid's text *correctness* on Chinese content
specifically at full-window coverage — §15's stress run only ever
matched Hybrid to Chinese content at 60.9% coverage (`sample_e`) with a
much lower CER (0.492) than this supplement's full-coverage run (1.166)
on the *same* entry, suggesting CER got markedly worse, not better, as
more of the window was actually processed — the opposite of what
partial-coverage undersampling would predict if the effect were random.

### Explicit distinction from the original five-window stress run

| | §15 stress run | §16 completion supplement |
|---|---|---|
| Entries | 5 (`g`, `e`, `h`, `f`, `c`) | 3 (`g`, `e`, `a`) |
| Profile | Split (Hybrid: g/e; Production: h/f/c) | Hybrid only |
| Timeout | 600 s | 1800 s |
| Result file | `evaluation_results.json` | `evaluation_results_completion_supplement.json` |
| Outcome | All 5 `partial_timeout` | All 3 `completed` |
| Status | Final, unchanged by this section | Final, additive |

`sample_h`, `sample_f`, `sample_c` remain exactly as §15 reported them —
partial, un-supplemented. This section does not close that gap.

### Human Adjudication — carried forward and added to

Items 1–4 from §15 stand unchanged (the timeout decision for `h`/`f`/`c`,
`sample_h`'s inconclusive duplicate-cue check, the Hybrid/Production
performance-gap confound, and how to fold partial results into
`EVALUATION_REPORT.md`). Add:

5. **The CER > 1.0 finding on Hybrid's Chinese-language output is new and
   unresolved.** It was not present as clearly in §15's partial-coverage
   Hybrid data and is now measured twice (`sample_e`, `sample_a`) at full
   coverage. This is a correctness question, not a coverage question —
   whether it warrants investigation, and on what timeline relative to
   M11's other stages, is for the gate to decide. Nothing about it was
   investigated, diagnosed, or fixed in this round.

### Historical transition to the Caption Identity Gate

Item 5 above historically triggered the **Caption Identity Corrective Gate**,
which subsequently investigated the root cause in product code (hybrid state
transition timing and multi-frame consensus disambiguation), implemented formal
fixes in `src/glyphcue/application/`, and verified correctness across 843
passing tests at gate closure (commit `875fb04`; current repository baseline is
902 passed, 1 skipped, 1 xfailed).

---

## 17. Bilingual completion supplement (Architecture B + DirectML product path) — results and Stage ⑤ closure

**This section completes the representative evaluation evidence for the three
bilingual frozen windows (`sample_h`, `sample_f`, `sample_c`).**

Following the integration of Multilingual Architecture B (shared detection +
universal recognition), the P2/P3/P4B DirectML acceleration adapters, and the
clustering ambiguity fix (`075ac4b`), the three bilingual windows were evaluated
over their full 180.0 s spans under the formal Architecture B + DirectML product
path (`DirectMlOcrEngine` + `DirectMlTextDetector`, `build_multilingual_ocr_evidence_job` →
`reconstruct_multilingual_cues_for_track_group`). Run from an isolated `[directml]`
venv with pinned `rapidocr==3.9.2` and `onnxruntime-directml==1.24.4` (`DmlExecutionProvider`
confirmed active, 1800 s timeout per window).

### Result: all three completed 180/180 s

Results written to `private_samples/m10_video_corpus/evaluation_results_bilingual_directml_supplement.json`:

| Entry | Window | Completion | Coverage | Point recall | Mean CER (zh / en) | Cues / Obs | Realtime ratio | Wall clock | Ambiguous cues |
|---|---|---|---|---|---|---|---|---|---|
| `sample_h` (bilingual, fixed footer) | 900–1080 s | **succeeded** | 180/180 s (100%) | **10/10 (100%)** | zh 0.2523 / en **0.0183** | 160 / 1306 | **2.71×** | 488.1 s (8.1 min) | 17 / 160 (10.6%) |
| `sample_f` (bilingual, fast b-roll) | 560–740 s | **succeeded** | 180/180 s (100%) | **11/11 (100%)** | zh **0.0611** / en 0.4641 | 399 / 2444 | **3.66×** | 659.2 s (11.0 min) | 78 / 399 (19.5%) |
| `sample_c` (bilingual, mixed format) | 480–660 s | **succeeded** | 180/180 s (100%) | **10/10 (100%)** | zh 0.1316 / en 0.4316 | 143 / — | **4.16×** | 748.2 s (12.5 min) | 31 / 143 (21.7%) |

Total wall clock for the three bilingual windows: 1895.4 s (31.6 min).

### Analysis of empirical results

1. **Coverage and Realtime Target (≤5×):**
   Every bilingual window processed 180/180 s (100.0% media coverage).
   All three windows measured well within the M11 performance target of ≤5.0× realtime
   (2.71×, 3.66×, 4.16×). This resolves the CPU baseline's ~99–159× (pre-Architecture-B)
   and 7.4×–14.0× (CPU Architecture B) bottlenecks.

2. **Multilingual Layer Separation & Ground Truth Point Recall:**
   - **Point recall:** 100.0% across all 31 verified ground-truth instants (10/10 on `h`, 11/11 on `f`, 10/10 on `c`).
   - **Multilingual layer-assignment errors:** `multilingual_missing_layer_count = 0`, `multilingual_wrong_assignment_count = 0` across all 31 instants.
   - **Layer swap:** 0 occurrences in normal conversational dialogue across all three windows. The layer-swap defect diagnosed in `075ac4b` is confirmed resolved under full-window conditions.

3. **Residual Finding — `sample_c` isolated `"3\n8"` reading:**
   - At 480.00–481.10 s (Cue 1, duration 1.10 s), the Chinese layer emitted `"3\n8"` (ground truth: `"你只需成为言出必行之人。"`), flagged with `ambiguous_languages: ["zh"]`.
   - In the immediately following Cue (481.10–481.67 s), the Chinese layer cleanly recovered `"你只需成为言出必行之人。"` with CER 0.0 and no ambiguity flags.
   - Across the remaining 142 Cues (482–660 s), `"3\n8"` never recurred. 7 of the 10 verified instants in `sample_c` achieved perfect 0.0000 Chinese CER.
   - **Adjudication:** This is an isolated window-boundary non-text OCR noise artifact that fail-closed safely under the ambiguity diagnostic; it does not systematically contaminate user output or downstream cues. Preserved as a documented limitation, not masked.

4. **Cue Density and Cadence:**
   - `sample_h`: 160 Cues across 180 s (mean duration 1.10 s). The fixed footer strip (`PURPOSE`) is admitted by the ROI and retained in the English layer; no cross-video leakage.
   - `sample_f`: 399 Cues across 180 s (mean duration 0.45 s). Reflects the fastest cadence in the corpus (49 changes/min) combined with rapid b-roll screen recording cuts. In 618–622 s, rich-text editor buttons (`B I U S ミ H1 H2`) appeared on screen and were recognized into `zh` with `ambiguous_languages: ["zh"]`.
   - `sample_c`: 143 Cues across 180 s (mean duration 1.26 s). Dense statistic overlay box at 552 s successfully extracted.

### Human Adjudication Closure

On 2026-09-03, human adjudication formally reviewed the evidence from §15, §16, and §17:
* All five frozen representative windows (`sample_g`, `sample_e`, `sample_h`, `sample_f`, `sample_c`) plus clean baseline `sample_a` have completed 180 s full-window evaluations.
* Acceptance Gate 9 (transferred from M10 §17) is satisfied.
* **Milestone 11 Stage ⑤ Representative Evaluation is formally CLOSED.**
* At this point in the record, Milestone 11 remained **IN PROGRESS**, with Stage ⑥ Full Regression next. **Update:** Stage ⑥ subsequently closed by Human Adjudication (2026-09-03), Stage ⑦ produced real packaging/DirectML-default evidence (2026-09-04), and Milestone 11 itself then **CLOSED (2026-09-04) with Release Acceptance REJECTED BY HUMAN ADJUDICATION** — see `PROJECT_STATUS.md` and `ROADMAP.md` §18 for the full closure disposition; the product is now in Milestone 12 (Product Rework & Cue Quality Recovery, `ROADMAP.md` §19).

