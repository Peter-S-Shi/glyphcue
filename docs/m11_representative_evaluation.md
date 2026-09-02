# Milestone 11 — Representative Evaluation (stage ⑤)

**Status:** IN PROGRESS. This document currently covers **step 1 only —
corpus selection**. No evaluation run has been executed yet.

**Scope of this step:** a read-only inventory of the eight private sample
videos in `private_samples/m10_video_corpus/`, and a recommended
evaluation corpus of 3–5 videos × one 2–5 minute window each, chosen for
complementary coverage rather than volume.

**Not done here, deliberately:** no full evaluation run, no OCR algorithm
change, no reopening of Beta-S / Auto-ROI research, no retuning of the
0.300 threshold, no promotion of the Experimental Hybrid profile. Nothing
under `src/` was touched by this step.

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

## 5. Open items for the rest of stage ⑤

- Ground truth does not exist for the `sample_e` / `sample_f` /
  `sample_g` / `sample_h` windows. Decide, before running, whether to
  build point-sample ground truth in M10's format or to report those four
  windows qualitatively — and say which in `EVALUATION_REPORT.md`.
- Per-window ROI has not been proposed. `sample_g` needs one that
  excludes the overlay cards; `sample_h` needs one that excludes the
  fixed footer strip.
- The corpus must be run through the hardened harness
  (`benchmarks/_job_harness.py`). The M10 crash condition
  (`docs/m10_private_corpus_incident.md`) has not been re-verified
  against these specific windows.
- Human gate: confirm these five windows and their framing before any
  large run starts.
