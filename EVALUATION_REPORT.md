# Evaluation Report

Required by ROADMAP.md §17. This report **compiles committed M3–M10
benchmark evidence alongside M11 Stage ⑤ representative evaluation
outcomes** — numbers originate from real benchmark runs, QA/ADR records,
incident investigations, and M11 Stage ⑤ evaluation runs. Where a metric
lacks empirical closure on a given corpus, this report states that
boundary explicitly rather than approximating one.

## How to read this report

Every result below is tagged along four axes that must not be conflated:

1. **Controlled/synthetic vs. realistic-private evidence.** Controlled/
   synthetic corpora (rendered text, hand-authored fixtures, generated
   degradation) are built and fully controlled by GlyphCue's own test
   authors. The realistic-private corpus (`private_samples/m10_video_corpus/`,
   gitignored, never committed) is the repo owner's own real, private
   video material — the primary source of external-realistic evidence in
   this report, for which M11 Stage ⑤ has completed full-window runs on
   `sample_g`, `sample_e`, and reserve `sample_a`, while `sample_h`,
   `sample_f`, and `sample_c` remain partial (see "Corpus" and "M11 stage 5" below).

2. **TDD/non-held-out fixtures vs. comparative or external-realistic
   evidence.** Several corpora (Path B's 17-case fixture, the
   consensus/multilingual synthetic scenarios) are the *same* corpus the
   implementation was built and corrected against — a reproducible
   regression check, not a generalization claim. Comparative baselines
   (PaddleOCR vs. RapidOCR, selective vs. dense OCR, consensus vs.
   single-frame, Review Priority vs. random) and the realistic-private
   corpus are evidence of a different, stronger kind: built or observed
   independently of the mechanism being judged.
3. **Measured results vs. design rationale/inference.** Most numbers here
   are direct measurements. A few decisions (ADR 0005's multilingual
   timing simplification; the "M11 candidate improvements" ranking in
   the performance section) are stated as design rationale or inference
   from measured evidence, not themselves a benchmarked measurement —
   each is labeled as such at the point it appears.
4. **Production-pipeline findings vs. evaluation-harness findings.** The
   private-corpus crash (`docs/m10_private_corpus_incident.md`) produced
   both kinds in one incident: a real bug in the *evaluation harness*
   (now fixed, `benchmarks/_job_harness.py`) and a real, if partial,
   signal about *production* `ChangeTriggeredOcrPolicy` trigger-rate
   behavior on real material. These are kept distinct throughout.

---

## Corpus

| Corpus | Type | Ground truth | Status |
|---|---|---|---|
| Path B fixtures (`benchmarks/path_b_normalization/`) | Hand-authored, controlled/synthetic | Independently authored, exact-match | Complete — same corpus implementation was built/corrected against (TDD, non-held-out); 17/17 cases pass |
| OCR runtime selection corpus (`benchmarks/ocr_runtime_selection/`) | Generated, controlled/synthetic (in-script rendered text, 6 items incl. English/Chinese/Japanese/bilingual/low-quality/styled) | Independently known (the rendered source text) | Complete, comparative (PaddleOCR vs. RapidOCR) |
| Selective-OCR verification fixture (`benchmarks/selective_ocr_pipeline/`) | Generated, controlled/synthetic (40-frame fixture, 2 text segments + blank tail) | Independently known | Complete, comparative (selective vs. dense policy) |
| Multi-frame consensus corpus (`benchmarks/multi_frame_consensus/`) | Generated, controlled/synthetic (3 ground-truth lines, 5 degraded variants each, real PaddleOCR) | Independently known (rendered source text) | Complete, comparative (consensus vs. single-frame baseline); includes one deliberate worst-case scenario |
| Multilingual reconstruction corpus (`benchmarks/multilingual_reconstruction/`) | Generated, controlled/synthetic (bilingual + trilingual single-frame blocks, real PaddleOCR) | Independently known | Complete; both scenarios show 0 missing/wrong layers — see "Multilingual" below for why this is a coverage gap, not a clean bill of health |
| Review Priority evaluation corpus (`benchmarks/review_priority/`) | Generated, controlled/synthetic (200 synthetic Cues, noisy Observations, real reconstruction) | Derived automatically post-hoc from the synthetic ground truth (label-leak-free methodology) | Complete, comparative (Review Priority vs. random baseline) |
| M10 controlled video corpus (`benchmarks/m10_controlled_video_corpus/`) | Generated, controlled/synthetic (3 fixtures, 5.9s each) | Not applicable — used for performance diagnosis, not text accuracy | Complete for its stated purpose: reproducible performance-diagnosis only |
| **Realistic-private corpus** (`private_samples/m10_video_corpus/`) | **Real, private, copyrighted video** — the repo owner's own material | Independently verified point-samples (real captions read directly from extracted frames, not reverse-engineered from GlyphCue's own output) | **Incomplete — improved from M10.** M10's one attempt crashed after ~40 minutes on an evaluation-harness bug before any entry finished (`docs/m10_private_corpus_incident.md`). M11 stage 5 fixed that bug and ran a five-window split-profile evaluation to real completion (no exception): all five windows finished `partial_timeout` under a 600 s cap. A scoped completion supplement then re-ran three Hybrid-eligible windows at 1800 s, all of which finished — see "M11 stage 5" below. `sample_h`/`sample_f`/`sample_c` remain partial; ROADMAP §17's full target is still open. |

**ROADMAP §17's target envelope — "3–5 representative videos × 2–5 minute
segments" — was not closed by any corpus in this report.** M10's gate
audit (2026-08-31, ROADMAP.md §17) accepted M10 as complete while
transferring this specific target to Milestone 11 as a mandatory
acceptance gate, not waiving it. See "M10 evidence status / unresolved
items" at the end of this report.

Public demo-safe material: none identified beyond the copyright-safe
generated/rendered fixtures already listed above (per
`docs/m10_evidence_inventory.md` §1).

## Ground truth

- **Independently authored / rendered** (Path B fixtures, OCR runtime
  corpus, consensus corpus, multilingual corpus): ground truth text is
  known before any OCR or reconstruction runs — never derived from
  GlyphCue's own output.
- **Automatically derived, label-leak-free** (Review Priority corpus):
  ground truth Cue text is generated first from a random seed, noisy
  Observations are generated independently of any correctness label, and
  `is_error` is computed only after the real reconstruction seam has run
  — see `docs/qa/reconstruction_qa_review_priority.md` for the full
  methodology and the specific label-leak it replaced.
- **Independently verified point-samples** (realistic-private corpus):
  a small number of specific verified instants where the real on-screen
  caption text was read directly from extracted video frames — this
  supports point-recall and per-point CER *only*, not Cue-level
  precision or timing start/end error (see "Cue recovery" and "Timing"
  below for exactly why, and note this corpus never produced a scored
  run regardless).

## Metrics

Organized by ROADMAP §17's own named metric families.

### Text: CER / WER

- **CER** (`glyphcue.evaluation.metrics.character_error_rate`, canonical
  location since M10; originally `benchmarks/ocr_runtime_selection/cer.py`):
  measured and reported in three places —
  - OCR runtime selection: PaddleOCR 0.0 CER on all 6 corpus items
    (including Japanese and a degraded low-quality crop); RapidOCR 0.6429
    CER on Japanese (see "Baselines" below).
  - Multi-frame consensus: mean CER improved from 0.0522 (single-frame)
    to 0.0 (consensus) in the mixed-degradation scenario; worsened from
    0.0522 to 0.1052 in the deliberate all-degraded worst case (see
    "Negative/mixed findings").
  - Multilingual reconstruction: CER 0.0 on every language layer in both
    the bilingual and trilingual synthetic scenarios.
  - **Measured on realistic-private corpus under M11 Stage ⑤ supplement (pre-corrective baseline):**
    `sample_g` (EN) measured CER 0.163. `sample_e` (ZH) measured 1.166 and
    reserve `sample_a` (ZH) measured 1.679. Note: these Chinese CER measurements
    reflect the pre-corrective state that historically triggered the **Caption
    Identity Corrective Gate**, which subsequently root-caused and resolved
    the consensus/probe issue; they do not represent current post-fix quality.
    `sample_h`/`sample_f`/`sample_c` remain partial/unmeasured.
- **WER** (`glyphcue.evaluation.metrics.word_error_rate`): implemented
  and unit-tested (`tests/evaluation/test_metrics.py`) against known-good

  literal examples. **No benchmark applies it to any real or synthetic
  text corpus.** Stated per this report's own discipline: **not
  empirically closed** for any corpus — an implementation exists, no
  result does. CJK text has no natural word-boundary tokenization in
  this codebase (Path B's own merge logic joins CJK text structurally,
  never assumes a word boundary — see `docs/qa/reconstruction_qa_review_priority.md`),
  which is itself a reason WER has not been the metric of choice for the
  CJK-heavy corpora already evaluated by CER instead.

### Cue recovery: precision / recall

`glyphcue.evaluation.metrics.cue_recovery_precision_recall` is
implemented and unit-tested against known-good examples. **No benchmark
applies it to any Path A corpus.** The closest real evidence that
exists is conceptually adjacent, not the same metric:

- Path B's `over_merge_guard` category (5/5 pass — 4 English + 1 CJK) is
  real evidence against a **false-merge** failure mode, the practical
  analogue of precision for Path B's segmentation decisions.
- Path B's `rolling_reconstruction` category (8/8 pass — 5 English + 3
  CJK) is real evidence against a **missed-merge** failure mode, the
  practical analogue of recall.
- These are Path B, hand-authored, non-held-out evidence (`docs/qa/path_b_cjk_rolling_normalization.md`),
  not a Path A/OCR result, and not literally `cue_recovery_precision_recall`.

The realistic-private corpus's point-sample methodology could in
principle support a **point-recall** figure (did some real Cue cover
each verified instant at all) but explicitly **cannot** support Cue-level
precision (a sparse point sample cannot vouch for every real Cue GlyphCue
produces — an unmatched real Cue is not evidence of a false positive) —
this scope limitation is stated in the evaluation script's own docstring
(`benchmarks/private_video_corpus/run_evaluation.py`). In M11 Stage ⑤'s
completion supplement, point-recall was measured at 90–100% across 31
verified instants on the completed windows (`sample_g`, `sample_e`, reserve
`sample_a`). However, Cue-level precision remains unmeasured by design of
the sparse point-sample methodology.

**Stated per this report's own discipline: Path A Cue-level precision/
recall is not empirically closed on any corpus.**


### Timing: start error / end error

`glyphcue.evaluation.metrics.timing_error` is implemented, unit-tested,
and **has one real empirical result**: Path B's 3 timing-tagged cases in
the hand-authored 17-case corpus show 0.0s mean start/end error. This is
expected, not a generalization claim — these are hand-authored fixtures
with exact-match ground truth, the same corpus the implementation was
built against (`docs/qa/path_b_cjk_rolling_normalization.md`, "Milestone
10 addendum").

**No benchmark measures Path A (OCR/consensus) Cue start/end timing
error against independently-known ground truth on any corpus** — the
consensus and multilingual benchmarks measure only text CER, not timing
accuracy. **This is explicitly not empirically closed for Path A.**

The realistic-private corpus's ±1s point-sample windows are, by the
evaluation script's own stated design, **not** a claimed real Cue span
and cannot support a timing start/end error claim even in principle —
this is a scope limitation of the ground-truth methodology, not
something a completed run would have been able to report differently.

### Multilingual: layer separation errors / missing / wrong layer assignment

`glyphcue.evaluation.metrics.multilingual_layer_assignment_errors` is
implemented and unit-tested. The only real-PaddleOCR evidence that
exists (`benchmarks/multilingual_reconstruction/evaluation_results.json`)
covers two clean, single-frame, well-separated synthetic scenarios
(bilingual en+zh, trilingual en+zh+ja) — both show `missing_languages: []`
and CER 0.0 on every layer.

**This is a coverage gap, not a clean bill of health**: neither scenario
was constructed to be hard to classify, so a zero-failure result does
not establish the mechanism is robust against harder, real material. The
realistic-private corpus's `_evaluate_entry` explicitly computes
`multilingual_missing_layer_count` and `multilingual_wrong_assignment_count`
per entry for exactly this reason. In M11 Stage ⑤'s stress run, the bilingual
windows (`sample_h`, `sample_f`, `sample_c`) ran under `PRODUCTION_TRIGGER`

and timed out at 2.2%–3.5% window coverage; they matched only 3 real bilingual
instants (1 miss, 2 non-misses), leaving real-world multilingual layer
separation narrowed but not yet closed at scale (`FAILURE_MODE_REPORT.md` #5
has the full analysis). The M6 implementation doc additionally states,
as an already-known limitation independent of this report: script detection
covers only Han/Kana/Latin (no claim for Cyrillic, Arabic, Devanagari, etc.),
and a cluster with zero decisive/eliminated evidence falls back to geometry-only
guessing, "not yet measured against a real target sample exhibiting this"
(`docs/multilingual/track_group_reconstruction.md`).

**Stated per this report's own discipline: multilingual layer-assignment
correctness against real, non-synthetic material is not empirically
closed in either direction** — neither confirmed working nor confirmed
failing.

### Path B: duplicate-removal / segmentation / timing normalization

All three have real, hand-tagged results on the same 17-case corpus
(`docs/qa/path_b_cjk_rolling_normalization.md`, "Milestone 10 addendum";
raw: `benchmarks/path_b_normalization/evaluation_results.json`;
regression-locked: `tests/application/test_path_b_normalization_evaluation.py`):

| Metric | Cases tagged | Result |
|---|---|---|
| Duplicate-removal correctness | 2 | 2/2 pass |
| Segmentation correctness | 14 | 14/14 pass |
| Timing normalization | 3 | 3/3 pass, mean start/end error 0.0s |

Same caveat as elsewhere: hand-authored, exact-match, non-held-out
corpus — the value is the reproducible, categorized breakdown of
deliberately adversarial edge cases, not a claim of generalization
beyond this corpus.

### Performance

Real, isolated measurements on the M10 controlled/synthetic corpus
(`docs/m10_performance_diagnosis.md`,
`benchmarks/m10_controlled_video_corpus/performance_diagnosis_results.json`),
all using real, unmodified production seams:

| Stage | Measurement |
|---|---|
| Pure frame decode (PyAV, no OCR) | 171–358 frames/sec |
| Real `PaddleOcrEngine.recognize()` call | mean 2.9–3.3s, p95 3.7–6.4s |
| `PaddleOcrEngine` construction | 1.6–3.4s, one-time per engine |
| Persisting 1000 synthetic Observations | 143–147/sec |
| Harness event-loop/signal overhead | -0.008s to +0.010s (negligible) |
| Selective policy, wall/media ratio | 1.92×–6.44× realtime (small, mostly-static clips) |
| Dense policy (control only), wall/media ratio | 40.6×–166.4× realtime |

**Processing speed / frames-analyzed-per-second / OCR-calls-per-minute**
are all covered by the table above and its source JSON.

**CPU use**: **not measured anywhere in M10.** No benchmark or diagnosis
script records CPU utilization (only wall-clock time). Stated as not
empirically closed.

**Memory — two genuinely different things, not to be conflated:**
- **M3 OCR-runtime memory/startup** (`docs/adr/0001-ocr-runtime-selection.md`):
  process RSS before/after model load, `max_observed_rss_mb` (documented
  as an approximation, not a true peak) — PaddleOCR ~368–789MB vs.
  RapidOCR ~70–116MB; PaddleOCR startup (import + construction, warm-up
  excluded) 4.57s vs. RapidOCR 1.55s. **This measures the OCR engine in
  isolation, constructed standalone by the benchmark script — not the
  full GlyphCue pipeline (UI, job orchestration, persistence, decode all
  running together).**
- **Full-pipeline memory/CPU**: **not measured anywhere in M10.** No
  diagnosis captures RSS or CPU while the real end-to-end job
  (decode → OCR → reconstruction → persistence) runs together. Stated as
  not empirically closed — the M3 numbers above must not be read as a
  stand-in for this.

**Package/runtime cost**: PaddleOCR ~590MB installed footprint (packages
+ downloaded models) vs. RapidOCR's ~212MB (`docs/adr/0001-ocr-runtime-selection.md`)
— a real, accepted cost of the OCR-runtime decision, explicitly flagged
in that ADR as a Windows-packaging consideration for Milestone 11/12.

### Review Priority

Full methodology and numbers: `docs/qa/reconstruction_qa_review_priority.md`
("Evaluation"), `benchmarks/review_priority/evaluation_results.json`.

**Error-capture curve / top-N recall vs. random baseline** (200-Cue
synthetic corpus, label-leak-free, real reconstruction seam, 20-seed
averaged random baseline):

| Top fraction | Review Priority recall | Random baseline | Beats random? |
|---|---|---|---|
| 10% | 7.5% | 9.75% | No |
| 20% | 20.0% | 19.75% | Yes |
| 30% | 30.0% | 31.75% | No |

**Missed failure classes** (M10 addendum, same corpus/scoring, no
re-tuning): splitting the 40 real wrong Cues by which `ReviewPriority`
component fired shows the aggregate result above is not uniform —
`low_confidence_and_other_signal` (34/40) beats random at 2 of 3 cuts;
`low_confidence_only` (6/40) never beats random at any cut (0% vs.
10.8–28.3% random). `no_signal` (zero components fired) never occurred
among the 40 wrong Cues. Full detail: `FAILURE_MODE_REPORT.md` #1–#2.

**Scope, stated precisely** (already stated in the source doc, repeated
here): this evaluates the ranking mechanism in a specific synthetic
multi-reading-per-Cue scenario run through the real reconstruction seam
— not a claim about real-world OCR/subtitle error rates. It is Path
A/OCR-shaped; Path B has no comparable per-Cue diagnostics to rank by, so
no equivalent evaluation exists for Path B.

---

## Baselines (comparative evidence)

| Comparison | Result | Evidence |
|---|---|---|
| **PaddleOCR vs. RapidOCR** | PaddleOCR: 0.0 CER on all 6 items. RapidOCR: 0.6429 CER on Japanese (disqualifying — no Japanese-specific model in its default package), competitive elsewhere. PaddleOCR footprint/startup cost materially higher (see "Performance"/"Memory" above). | `docs/adr/0001-ocr-runtime-selection.md`, `docs/benchmarks/ocr_runtime_selection.md` |
| **Selective vs. dense OCR** | Selective: 3 OCR calls, 2 observations (exact match to ground truth), 13.64s. Dense: 40 OCR calls, 30 observations, 101.27s. **92.5% OCR-call reduction**, no missed text. | `docs/adr/0002-selective-ocr-strategy.md` |
| **Consensus vs. single-frame baseline** | Mixed-degradation scenario: mean CER improved 0.0522 → 0.0. Deliberate all-degraded worst case: mean CER worsened 0.0522 → 0.1052 (see "Negative/mixed findings"). | `docs/adr/0003-consensus-reconstruction-approach.md`, `docs/consensus/multi_frame_consensus.md` |
| **Review Priority vs. random** | Roughly at parity overall (beats random at 1 of 3 cuts); beats random at 2 of 3 cuts for the majority failure class, never beats random for the `low_confidence_only` class. | `docs/qa/reconstruction_qa_review_priority.md` |

---

## Negative / mixed results (preserved, not tuned away)

All of the following are real, already-committed findings, reported
honestly at the time they were produced and preserved here unchanged:

1. **Review Priority overall ranking is roughly at parity with random**
   (beats it at only 1 of 3 top-fraction cuts). See "Review Priority"
   above; full detail `FAILURE_MODE_REPORT.md` #2.
2. **Review Priority's `low_confidence_only` failure class never beats
   random at any cut** (0% vs. 10.8–28.3%). `FAILURE_MODE_REPORT.md` #1.
3. **Consensus voting makes CER measurably worse in a deliberate
   all-degraded worst case** (0.0522 → 0.1052), confined to a constructed
   scenario that withholds `state_trigger` evidence a real
   `ChangeTriggeredOcrPolicy` run would provide. `docs/consensus/multi_frame_consensus.md`
   ("Failure modes").
4. **The controlled noisy-background fixture did not reproduce the real
   corpus's elevated OCR-trigger rate** (3 triggers, identical to the
   clean fixture, vs. 177 triggers observed in the one real partial
   private-corpus entry). `FAILURE_MODE_REPORT.md` #9,
   `docs/m10_performance_diagnosis.md`.
5. **The private-corpus evaluation harness crashed** after ~40 minutes
   on its own concurrency bug — a harness failure, now fixed, kept
   distinct from the separate, real production finding it partially
   confounded (elevated real-world OCR-trigger rate). `FAILURE_MODE_REPORT.md`
   #6–#7, `docs/m10_private_corpus_incident.md`.
6. **Even the best-case (selective) policy runs slower than realtime**
   on small, mostly-static synthetic clips (1.92×–6.44×), driven by
   PaddleOCR's ~3s/call structural cost, not decode/persistence/harness
   overhead. `FAILURE_MODE_REPORT.md` #8, `docs/m10_performance_diagnosis.md`.
7. **ADR 0005's multilingual timing simplification has no dedicated
   benchmark behind it** — a design-time claim from ROADMAP §4, not a
   measured comparison. `FAILURE_MODE_REPORT.md` #10 (design
   rationale/inference, not a measurement, per axis 3 above).

The full taxonomy, including two resolved M3 dependency-level failures
(PaddleOCR's mkldnn crash, RapidOCR's Japanese failure) and the
multilingual/representative-video evidence gaps, is in
`FAILURE_MODE_REPORT.md`.

---

## Build vs. Integrate

Full table: `BUILD_VS_INTEGRATE.md`. In summary: PaddleOCR (OCR
recognition), PyAV (media decode), Qt/PySide6 (threading/UI), and
pysubs2 (subtitle file I/O) are integrated mature dependencies, each
wrapped behind a GlyphCue-owned boundary (`OcrEngine`, the media-source
adapter, `Job`/`JobContext`, `Pysubs2SubtitleFormatAdapter`). GlyphCue's
own custom, non-library contribution is concentrated in: the
change-triggered OCR gating policy (M4), multi-frame consensus voting
(M5), multilingual layer separation (M6), Path B rolling/CJK
normalization (M8), and Review Priority ranking (M7) — none of these
five have an off-the-shelf equivalent integrated instead; each is a
from-scratch algorithm with its own evaluated evidence, cited throughout
this report.

## Limitations

- **Path A has no empirically-closed Cue-level precision/recall or
  timing start/end error result on any corpus** — implementations exist,
  no benchmark applies them (see "Cue recovery", "Timing" above).
- **WER has no empirically-closed result on any corpus** — implemented,
  unit-tested, never applied to a real evaluation corpus.
- **Multilingual layer-assignment correctness against real, non-synthetic
  material is unverified in either direction** — the only real-PaddleOCR
  evidence is two clean synthetic scenarios with zero observed failures,
  which is a coverage gap, not a robustness finding.
- **CPU use and full-pipeline memory are not measured anywhere in M10** —
  only OCR-engine-in-isolation memory/startup (M3) and wall-clock
  performance (M10 controlled corpus) exist.
- **Every controlled/synthetic corpus in this report is small and, in
  most cases, the same corpus its implementation was built and corrected
  against** — reproducible regression evidence, not a generalization
  claim, stated explicitly at each corpus's own entry above.
- **The realistic-private corpus produced only partial scored results.**
  M11 stage 5 (below) closed the evaluation-harness gap that blocked M10
  entirely, and real scored data now exists for a subset of the target
  corpus — but three of the five frozen windows (`sample_h`, `sample_f`,
  `sample_c`) are still timeout-limited to under 4% window coverage, and
  the two Chinese windows that did complete surfaced a correctness finding
  that historically triggered the Caption Identity Corrective Gate (subsequently
  investigated and resolved; see "M11 stage 5" below). `sample_h`/`sample_f`/`sample_c`
  coverage remains partial and Stage ⑤ remains open.

---

## M10 evidence status / unresolved items

- **ROADMAP §17's "3–5 representative videos × 2–5 minute segments"
  target was not completed in M10 — and, per M10's gate audit
  disposition (ROADMAP.md §17, 2026-08-31), this target is not waived.
  It is transferred to Milestone 11 as a mandatory acceptance gate**
  (ROADMAP.md §18's acceptance gate 9), because completing it safely
  requires exactly the Path A performance/harness work M11 Product
  Hardening already exists to do. The controlled/synthetic corpus
  (`benchmarks/m10_controlled_video_corpus/`) satisfies **reproducible
  performance diagnosis only** — it does not satisfy the
  representative-video target and is not presented as equivalent to it.
  M10's one real attempt against the repo owner's realistic-private
  corpus supplied only partial external-realistic evidence before
  crashing on an evaluation-harness bug (`docs/m10_private_corpus_incident.md`)
  — see "M11 stage 5" immediately below for what has since run.

### M11 stage 5 — Representative-Video Evaluation (partial; gate 9 still open)

Full detail, per-window numbers and the human-adjudication list:
`docs/m11_representative_evaluation.md` §15–§16. Summarized here per the
disposition above: fold results back into this report as they are
produced, whatever they are.

**Five-window split-profile stress run** (all five ⑤-A/⑤-B frozen
windows, 600 s per-entry timeout, no exception, harness bug from M10
confirmed fixed): every window finished `partial_timeout` —
`ChangeTriggeredOcrPolicy` ("Production Trigger", run on the three
bilingual windows `sample_h`/`sample_f`/`sample_c`) covered only
2.2%–3.5% of its 180 s window before the timeout; `EXPERIMENTAL_HYBRID`
(run on the two single-language windows `sample_g`/`sample_e`) covered
50.2%–60.9%. This is the M10 performance-cost finding (see
`docs/m10_performance_diagnosis.md`, and `FAILURE_MODE_REPORT.md` #7)
reproduced directly on five real windows rather than inferred from one
crash-truncated entry, and the Hybrid/Production coverage gap is
reported as a signal, not a conclusion — the two groups also differ in
content (single- vs. multi-language), so this run cannot separate
"Hybrid is faster" from "these two windows are easier."

**Completion supplement (pre-corrective historical measurement)** (`sample_g`,
`sample_e` at their unchanged window/ROI, plus the pre-existing M10 `sample_a`
clean-baseline reserve reused verbatim — Hybrid only, 1800 s timeout,
human-gate-approved): **all three completed** (real `succeeded` state,
not a timeout cancellation), with point recall 90–100% across 31 verified
instants. **Mean CER on the two Chinese-language entries measured above 1.0
in this pre-corrective run** (`sample_e`: 1.166, `sample_a`: 1.679) —
by definition of `character_error_rate` (edit distance / reference length,
unbounded above 1), the recovered text at matched instants diverged from
the short verified reference by more edits than the reference itself
contained. `sample_g`'s English CER (0.163) was normal.
**This pre-corrective measurement served as the historical trigger for the
Caption Identity Corrective Gate**, which subsequently investigated the root cause
(hybrid state transition timing and multi-frame consensus disambiguation),
implemented formal product fixes in `src/glyphcue/application/`, and verified
correctness across 843 passing regression tests. **These pre-corrective numbers
are historical evidence and cannot masquerade as the current post-fix quality
verdict.** Subsequent M11 performance hardening completed P2 recognition-only,
P3 Windows DirectML recognizer, and P4B Windows DirectML same-detector text detector
acceleration, while parallel chunking was evaluated via evidence gate and
formally rejected.



**Not yet attempted:** a longer-timeout supplement for `sample_h`,
`sample_f` or `sample_c` (still open — see the human-adjudication list
in `docs/m11_representative_evaluation.md` §15/§16). ROADMAP §18's acceptance gate 9
remains open; whether the above is sufficient to consider it, or whether
fuller coverage is required first, is a human-gate decision, not made in
this report.

- Also open, restated from "Limitations" above: Path A Cue-level
  precision/recall, Path A timing start/end error, WER (any corpus), and
  CPU use / full-pipeline memory are all not empirically closed. None of
  these gaps were filled by generating new evidence for this report,
  per this report's own stated discipline. Multilingual layer-assignment
  correctness on real material is now narrowed, not closed — see
  `FAILURE_MODE_REPORT.md` #5's update.
- While the evaluation report itself was produced without modifying production
  algorithms, subsequent M11 corrective and performance work has integrated
  caption identity fixes and opt-in DirectML GPU accelerators into `src/`.

