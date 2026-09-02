# Milestone 11 — Representative Evaluation (stage ⑤)

**Status:** IN PROGRESS, at step **⑤-B Evaluation Preparation**.
No evaluation run has been executed yet.

| Step | State |
|---|---|
| ⑤-A Corpus selection | **CLOSED** — accepted at the human gate; the corpus below is frozen |
| ⑤-B Evaluation preparation | **IN PROGRESS** — ROI proposals (§6) and ground-truth candidate worksheets (§7) |
| ⑤-C Hardened harness run | not started; prerequisites in §8 |

**Frozen corpus (⑤-A):** `sample_g` 90–270 s, `sample_e` 150–330 s,
`sample_h` 900–1080 s, `sample_f` 560–740 s, `sample_c` 480–660 s.

**Not done here, deliberately:** no evaluation run, no OCR or temporal
pipeline change, no reopening of Beta-S / Auto-ROI research, no retuning
of the 0.300 threshold, no promotion of the Experimental Hybrid profile.
Nothing under `src/` has been touched by stage ⑤.

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

`sample_a`–`sample_d` additionally carry M10 point-sample ground truth in
the corpus manifest (10–20 verified instants each).
`sample_e`–`sample_h` have none yet.

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
