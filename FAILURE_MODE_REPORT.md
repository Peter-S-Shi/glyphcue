# Failure Mode Report

Required by ROADMAP.md §17 acceptance gate 5: "failure taxonomy is
grounded in observed evidence." Every entry below points to a real,
already-committed artifact (a benchmark result, a QA/ADR doc, an
incident report) that actually produced the number or behavior cited.
No category was added to make this taxonomy look complete: a category
with no real observed instance is stated as such, not filled with a
plausible-sounding invented example.

Categories follow the split established in `BUILD_VS_INTEGRATE.md`:

- **A — Dependency/runtime limitations**: cost or behavior inherent to an
  integrated mature dependency (PaddleOCR, Qt, pysubs2), not fixable by
  changing GlyphCue's own code.
- **B — GlyphCue orchestration/reconstruction limitations**: GlyphCue's
  own code (job scheduling, OCR-trigger policy, consensus voting,
  multilingual layer separation, Path B normalization, Review Priority)
  not meeting a goal on some observed input.
- **C — Evaluation-harness failures**: bugs in `benchmarks/` scripts
  themselves — not shipped product code — that corrupted or prevented an
  evaluation run.
- **D — Evidence/corpus limitations**: gaps in what has actually been
  tested (synthetic-only corpora, non-held-out hand-authored fixtures, a
  real-data run that crashed before producing results, a negative
  reproduction attempt, an un-benchmarked ADR claim) — a coverage gap,
  not a code defect.

---

## 1. Review Priority: `low_confidence_only` failure class never beats random review

**Category: B — GlyphCue reconstruction/ranking limitation.**

Splitting the M7 Review Priority evaluation's 40 real wrong Cues (out of
213 reconstructed, from noisy Observations run through the real,
unmodified `reconstruct_cues_with_consensus`) by which real
`ReviewPriority` component fired:

| Failure class | Count | Top-10% | Top-20% | Top-30% |
|---|---|---|---|---|
| `low_confidence_and_other_signal` | 34/40 | 8.8% vs 9.6% random — No | 23.5% vs 19.7% — **Yes** | 35.3% vs 32.4% — **Yes** |
| `low_confidence_only` | 6/40 | 0% vs 10.8% — No | 0% vs 20.0% — No | 0% vs 28.3% — No |

The majority class (34/40) genuinely beats random at 2 of 3 cuts. The
`low_confidence_only` class (6/40) never beats random at any cut — when
6 identically-noisy-but-non-disagreeing readings still land on the wrong
answer, `ocr_confidence` is Review Priority's only remaining signal, and
in this corpus it never ranks those Cues above chance.

**Root cause, already diagnosed, not re-litigated here**: `had_disagreement`
is a coarse boolean that fires on ANY noise at all, so it cannot
distinguish "harmless minority noise the vote correctly resisted" from
"the vote genuinely failed." `ConsensusDiagnostics.agreement_ratio` (a
real, already-computed diagnostic) would likely discriminate this better,
but wiring a new signal into `compute_review_priority` was explicitly out
of the M7 corrective pass's mandate and remains unimplemented.

**Evidence**: `docs/qa/reconstruction_qa_review_priority.md` ("Milestone
10 addendum"), `benchmarks/review_priority/evaluation_results.json`
(`top_fraction_recall_by_failure_class`, `missed_failure_classes`).

**Disposition**: not fixed in M10 (would require wiring a new signal —
scope change). Candidate for a future pass; not routed to M11 performance
hardening since it is a ranking-quality question, not a scalability one.

---

## 2. Review Priority: overall ranking is roughly at parity with random review

**Category: B — GlyphCue reconstruction/ranking limitation.**

Before the failure-class split above, the aggregate result across all 40
wrong Cues: top-10% recall 7.5% vs. 9.75% random (no), top-20% 20.0% vs.
19.75% (yes, barely), top-30% 30.0% vs. 31.75% (no). `actual_error_rate`
in this run: 18.8% (40/213).

**Evidence**: `docs/qa/reconstruction_qa_review_priority.md`
("Evaluation" section), `benchmarks/review_priority/evaluation_results.json`.

**Disposition**: reported as an honest mixed/negative result at the time
of the M7 corrective pass, not tuned away. Superseded in interpretation
(but not in the underlying numbers, which are unchanged) by finding #1
above, which shows the aggregate parity result is not uniform across
failure classes.

---

## 3. Path B: genuinely ambiguous captions are never resolved — by design, not by omission

**Category: B — GlyphCue reconstruction limitation (a stated, evaluated design boundary, not a bug).**

`_classify_transition` deliberately refuses to merge two Observations
when it cannot find genuine temporal evidence for a rolling relationship,
even when their text coincidentally overlaps. Two named diagnostics exist
specifically for the cases GlyphCue will not guess at:

- `timing_collision` — real temporal overlap, no textual relationship.
- `segmentation_ambiguous` — a coincidental single-character text match
  that is not a full-prefix match.

Both are surfaced as `ReviewSignals.had_disagreement` (routed to human
review) rather than silently resolved either way. This is evaluated,
adversarial-by-design behavior (the "over-merge guard" category: 4/4
English + 1/1 CJK cases pass — i.e., these cases are correctly *not*
merged), not an unmeasured gap. The real limitation is structural: Path B
has no mechanism that can ever confidently resolve these cases on its
own — every genuinely ambiguous caption transition permanently requires a
human reviewer, by design.

**Evidence**: `docs/qa/path_b_cjk_rolling_normalization.md` ("The most
important fix: temporal eligibility", "Six named diagnostics"),
`benchmarks/path_b_normalization/evaluation_results.json`
(`over_merge_guard` category).

**Disposition**: correct, intentional, frozen behavior — not something
M10 proposes to change. Recorded here because "GlyphCue cannot resolve
this class of input" is itself a real, evidence-backed limitation of the
product's capability, distinct from a defect.

---

## 4. Path B evaluation corpus is hand-authored and exact-match, not held-out

**Category: D — Evidence/corpus limitation.**

The 17-case Path B corpus (100% pass rate; 0.0s timing error on the 3
timing-tagged cases) is the same corpus the implementation was built and
corrected against via TDD — not a held-out validation set. The 0.0s
timing error is expected on hand-authored, exact-match fixtures, not a
generalization claim about real captions.

**Evidence**: `docs/qa/path_b_cjk_rolling_normalization.md`
("Evaluation" section's own stated `scope_note`),
`benchmarks/path_b_normalization/evaluation_results.json`.

**Disposition**: stated as a scope boundary in the M8/M10 docs already;
repeated here because the failure taxonomy must not let a 100%-pass
number stand uncontextualized in `EVALUATION_REPORT.md`'s eventual
summary.

---

## 5. Multilingual missing/wrong-layer assignment: coverage gap narrowed, not closed — one real miss now observed

**Category: D — Evidence/corpus limitation (not a capability finding).**

**Updated 2026-09-02 (M11 stage 5).** M6's `MultilingualDiagnostics.missing_languages` /
`ambiguous_languages` mechanism exists specifically to flag layer
mis-assignment, and is unit- and synthetic-integration-tested. The two
real-PaddleOCR synthetic verification scenarios
(`benchmarks/multilingual_reconstruction/evaluation_results.json`:
bilingual en+zh, trilingual en+zh+ja) both show `missing_languages: []`
and CER 0.0 on every layer — clean, well-separated, single-frame,
synthetic-rendered text that never exercised a case that could actually
trip the mechanism.

M10's evaluation designed to observe this against real, messy material
crashed before producing a single data point (see #6). **M11 stage 5's
five-window split-profile stress run (`docs/m11_representative_evaluation.md`
§15) finally populated `multilingual_missing_layer_count` /
`multilingual_wrong_assignment_count` with real data — but the 600 s
per-entry timeout limited each of the three bilingual windows
(`sample_h`, `sample_f`, `sample_c`) to matching only ONE verified
ground-truth instant apiece.** Of those three: `sample_f`'s one matched
instant shows `multilingual_missing_layer_count: 1` (the reconstructed
Cue produced an English layer with no Chinese layer at all, at an
instant where the verified ground truth has both) — the mechanism's
first real observed miss. `sample_h` and `sample_c`'s single matched
instants each show 0 missing/wrong. **Sample size is still extremely
thin (n=3 matched real bilingual instants total)** — not enough to
characterize a rate, only enough to say the failure mode is real and
observable, which was previously unknown in either direction.

The M6 doc itself already states two adjacent, honest gaps in the same
direction: script detection covers only Han/Kana/Latin ("No claim about
non-CJK/non-Latin scripts" — Cyrillic, Arabic, Devanagari are
unsupported), and a cluster with zero decisive/eliminated evidence
"falls through to nearest-geometry leftover merge... not yet measured
against a real target sample exhibiting this."

**Evidence**: `benchmarks/multilingual_reconstruction/evaluation_results.json`,
`docs/multilingual/track_group_reconstruction.md` ("Failure modes / known
limitations"), `docs/m11_representative_evaluation.md` §15 (the stress
run's per-entry `multilingual_missing_layer_count` /
`multilingual_wrong_assignment_count`), `docs/m10_private_corpus_incident.md`.

**Disposition**: not a defect verdict either way — a coverage gap
narrowed by one real observed instance, not closed. Multilingual
layer-assignment correctness against real, non-synthetic material has
now shown one real miss and two real non-misses, on a sample far too
small to characterize a failure rate. Getting `sample_h`/`sample_f`/`sample_c`
to fuller coverage (open item in `docs/m11_representative_evaluation.md`
§15/§16's Human Adjudication list) is what would actually close this gap;
not attempted this round.

---

## 6. Private-corpus evaluation-harness crash: unbounded concurrent job execution

**Category: C — Evaluation-harness failure (not a product defect).**

`benchmarks/private_video_corpus/run_evaluation.py`'s original `_run_job`
helper quit only its local Qt event loop on timeout, never calling
`job.request_cancel()`. Once one entry's job overran its wait, the
script's sequential `for entry in entries:` loop started the *next*
entry's job while the previous one kept running, orphaned, on its own
background thread — turning an intended one-job-at-a-time run into
unbounded concurrent execution. The run crashed after 2404.5s (40.07 min)
wall clock with a `PermissionError` (an unclosed SQLite connection could
not be deleted by `tempfile.TemporaryDirectory` cleanup while a
still-running orphaned thread held it open).

**This is a bug in the evaluation harness's own job-orchestration code,
not in `glyphcue.jobs.Job`, `build_ocr_evidence_job`, or
`build_multilingual_ocr_evidence_job`** — the production cooperative-
cancellation contract works correctly when actually invoked (verified in
the controlled-corpus diagnosis run, where the fixed harness cancels an
overrunning job cleanly).

**Evidence**: `docs/m10_private_corpus_incident.md` (full root-cause
analysis, recovered per-entry evidence table).

**Disposition**: fixed. The harness's job runner is now the shared,
hardened `benchmarks/_job_harness.run_job_or_cancel`, which never returns
while a job's worker thread may still be alive — if a job does not reach
a terminal state within its cancellation grace period, it raises
`EvaluationJobDidNotTerminateError` and the run aborts before starting
the next entry (regression: `tests/benchmarks/test_job_harness.py`).
Applied to both `benchmarks/private_video_corpus/run_evaluation.py` and
`benchmarks/m10_controlled_video_corpus/run_performance_diagnosis.py`.

**Addendum, 2026-09-02 (M11 stage 5):** the fix has since carried real
production jobs through roughly 2.1 hours of combined real wall-clock
time across two runs (a five-entry, 600 s/entry stress run and a
three-entry, 1800 s/entry completion supplement — every timeout hit was
cancelled cleanly to a terminal state, no exception, no orphaned thread)
with no recurrence, and a dedicated `--crash-check` re-verified the exact
concurrency condition directly on all five real windows beforehand
(`docs/m11_representative_evaluation.md` §12). No further action.

---

## 7. Real-world OCR-trigger rate far exceeds anything the selective-OCR policy was calibrated against

**Category: B — GlyphCue orchestration limitation.**

**Updated 2026-09-02 (M11 stage 5): confirmed directly, on five real
windows, no longer inferred from one crash-truncated entry.** M10's one
real (crash-truncated) private-corpus entry, `private-a-clean-zh`,
triggered `ChangeTriggeredOcrPolicy` 177 times over only ~17.5 real
media-seconds — an implied rate of ~10.1 triggers/media-second. M11
stage 5's five-window stress run
(`docs/m11_representative_evaluation.md` §15) measured the same
`PRODUCTION_TRIGGER` path (`ChangeTriggeredOcrPolicy`) directly, to
completion of each job's timeout, on three real bilingual windows:
**`sample_h` 7.87 OCR calls/media-second, `sample_f` 9.16, `sample_c`
3.16** — the same order of magnitude as M10's single data point, now
from three independent real sources instead of one, and none of them
confounded by the concurrency bug #6 documents.

**The same run also gives the first direct, controlled-for-real-content
comparison against `EXPERIMENTAL_HYBRID`'s detector-anchored scheduling**
on the two Hybrid-eligible windows: `sample_g` 0.365 calls/s, `sample_e`
0.538 calls/s — roughly **1/15th–1/25th** the Production-trigger rate.
The completion supplement (§16, full-coverage run) reproduces the same
low Hybrid rate independently (`sample_g` 0.35/s, `sample_e` 0.561/s,
`sample_a` 0.706/s), so this is not a partial-coverage artifact. This
comparison is descriptive, not causal — the two profile groups are also
different content (single- vs. multi-language), so it does not by itself
attribute the gap to the trigger policy versus the detector-anchored
scheduler versus the content itself; see the Human Adjudication item in
`docs/m11_representative_evaluation.md` §15 on a controlled follow-up.

ADR 0002 already states, as an accepted known cost, that its
verification "does not claim the change-detection threshold is optimal
for... noisy compression artifacts... that would need a larger, more
varied evidence set" — this is now that larger evidence set, and it
confirms the gap rather than narrowing it.

**Evidence**: `docs/m10_private_corpus_incident.md` ("Product-pipeline
finding, kept distinct from the harness bug"), `docs/m10_performance_diagnosis.md`
("Connecting this back to the private-corpus incident"), `docs/adr/0002-selective-ocr-strategy.md`
("Known cost of the choice"), `docs/m11_representative_evaluation.md`
§15–§16 (per-window OCR/detector call counts and realtime ratios).

**Disposition**: not fixed (production behavior change forbidden under
Feature Freeze in M10; not attempted in M11 stage 5 either — this stage
is evaluation only, no OCR/temporal algorithm or threshold change). Still
ranked candidate #1 for a future M11 performance-hardening pass per
`docs/m10_performance_diagnosis.md`: "lower unnecessary OCR-call
frequency without changing reconstruction quality" — now backed by
directly-measured real-footage evidence rather than one crash-truncated
sample.

---

## 8. PaddleOCR per-call latency is the dominant, structural cost of the whole pipeline

**Category: A — Dependency/runtime limitation.**

Isolated measurement on controlled fixtures, real `PaddleOcrEngine`, real
production seams throughout: a single `recognize()` call on a tiny
480×160 crop costs a mean of 2.9–3.3s (median 2.2–3.6s, p95 3.7–6.4s)
across all 3 fixtures — consistent with ADR 0001's original per-item
latency numbers (2.3–3.3s). By contrast: pure frame decode runs at
171–358 fps, persisting 1000 Observations takes ~7ms each, and harness
event-loop overhead is sub-10-milliseconds in every measured run. None of
those are the bottleneck. As a direct consequence, even the **selective**
policy (production default) on small, mostly-static fixtures still ran
1.92×–6.44× slower than realtime; the **dense** control policy hit
40.6×–166.4× realtime before being cut off by its own timeout.

**Evidence**: `docs/m10_performance_diagnosis.md` (full bottleneck table),
`benchmarks/m10_controlled_video_corpus/performance_diagnosis_results.json`,
`docs/adr/0001-ocr-runtime-selection.md`.

**Disposition**: not fixed in M10 (no optimization implemented under
Feature Freeze). Ranked candidates #2–#3 in `docs/m10_performance_diagnosis.md`
(ROI size/downscale, runtime/model reuse across languages) target this
cost directly; #1 above reduces how often it is paid, not its per-call
cost.

---

## 9. Negative result: synthetic per-pixel noise does not reproduce the real corpus's elevated trigger rate

**Category: D — Evidence/corpus limitation (an honest negative finding, not a defect).**

The `difficult_noisy_background` controlled fixture (independent per-frame
random pixel noise over an otherwise-static background) was built
specifically to try to reproduce finding #7's elevated real-world trigger
rate in a controlled, reproducible way. It did not: it triggered exactly
3 times, identical to the clean fixture. Reasoned hypothesis, not
verified further: `ChangeTriggeredOcrPolicy`'s gate is presumably
mean-based (ADR 0002: "a commodity mean-absolute-pixel-difference
technique"), and independent, zero-mean random noise across a whole ROI
averages out to a small mean delta that does not cross the threshold —
whereas real camera motion is spatially *correlated*, not independent
per-pixel noise, and would plausibly produce a materially larger mean
delta.

**Evidence**: `docs/m10_performance_diagnosis.md` ("Negative result,
reported honestly").

**Disposition**: recorded as a genuine miss for this specific
reproduction attempt, not silently reworked until the numbers matched. A
fixture using structured motion (e.g. slow panning/drift) is the honest
next step if closer reproduction is needed — not attempted here.

---

## 10. Multilingual timing simplification's evidentiary basis is a design-time claim, not a benchmark

**Category: D — Evidence/corpus limitation.**

Unlike ADR 0001/0002/0003 (each backed by a specific benchmark script and
results file), ADR 0005's shared-Cue-level-timing simplification rests on
ROADMAP.md §4's own stated observation about the target material profile
— a product-scoping decision made before Milestone 0, not a benchmarked
comparison of "with alignment graph" vs. "without."

**Evidence**: `docs/adr/0005-multilingual-timing-simplification.md`
("Known cost of the choice").

**Disposition**: stated as an honest limitation in the ADR itself. If a
future representative sample surfaces a genuinely independent-schedule
case, that is new evidence against the simplification, not something
already ruled out by existing data.

---

## 11. PaddleOCR: a real CPU-compatibility crash, and a rejected alternative's real disqualifying failure

**Category: A — Dependency/runtime limitation.**

Two distinct, real, already-resolved dependency-level failures surfaced
during OCR runtime selection (M3), kept here because they are real
observed failures, not because they remain open:

- `PaddleOCR(...)` with its default `enable_mkldnn=True` raised
  `NotImplementedError` on this CPU with `paddleocr==3.7.0` /
  `paddlepaddle==3.3.1`. Worked around (`enable_mkldnn=False`, baked into
  `PaddleOcrEngine`'s construction) — a real, version-pairing-specific
  bug that must be re-verified on any future dependency upgrade.
- The rejected alternative, RapidOCR, failed Japanese outright (CER
  0.6429 — it dropped most of the hiragana) because its default
  installable package ships no Japanese-specific recognition model. This
  was disqualifying given GlyphCue's stated Japanese requirement, not a
  minor accuracy gap.

**Evidence**: `docs/adr/0001-ocr-runtime-selection.md` ("Known cost of
the choice", "What was rejected"), `docs/benchmarks/ocr_runtime_selection.md`.

**Disposition**: both resolved by the M3 runtime-selection decision
itself (PaddleOCR chosen, mkldnn workaround shipped). Recorded for
completeness since both are real, observed dependency failures that
directly shaped a frozen architectural decision.

---

## 12. Experimental Hybrid: Chinese-language recognition CER exceeds 1.0 at full window coverage

**Category: B — GlyphCue orchestration limitation (resolved via Caption Identity
Corrective Gate, commit `875fb04`).**

M11 stage 5's completion supplement
(`docs/m11_representative_evaluation.md` §16) ran `EXPERIMENTAL_HYBRID`
to real, full-window completion (`succeeded`, not a timeout cancellation)
on three windows for the first time: `sample_g` (English), `sample_e`
and `sample_a` (both Chinese). Point recall was strong across all three
(90–100% of verified instants matched). But **mean character error rate
on the two Chinese entries measured above 1.0** — `sample_e`: 1.166,
`sample_a`: 1.679 — while `sample_g`'s English CER (0.163) stayed in a
normal range. Since `character_error_rate` is Levenshtein edit distance
divided by reference length with no upper bound, a value above 1 means
the recovered text at a matched instant diverges from the short verified
reference by *more* edits than the reference itself contains — consistent
with recovered text substantially longer than, or substantially
different in content from, the single caption line it was supposed to
match.

Two observations narrow, but do not confirm, where this came from:
`sample_a` (CER 1.679, the worse of the two) also has the highest
observations-per-Cue ratio of the three completed entries (635
observations across 92 Cues, vs. `sample_e`'s 215/89 and `sample_g`'s
110/37) — consistent with, but not proof of, `hybrid_evidence_job`'s
"ONE recognition per state" design merging a wider span of real captions
into a single recognized block than any one verified instant's reference
text covers. Separately, `sample_e`'s own CER got *worse* going from
partial coverage in the five-window stress run (0.492 at 60.9% window
coverage, §15) to full coverage in the completion supplement (1.166 at
100%, §16) on the *identical* entry — the opposite of what undersampling
alone would predict, which argues against "just not enough data yet" as
the explanation.

**Evidence**: `docs/m11_representative_evaluation.md` §15–§16 (full
per-entry numbers, both the stress-run and completion-supplement
readings for `sample_e`), `src/glyphcue/application/hybrid_evidence_job.py`
(module docstring, "ONE recognition per state").

**Disposition**: initially recorded as a real correctness finding specific to Hybrid's
Chinese-language output at full coverage.
*(Reconciliation Update 2026-09-03: Investigated, root-caused, and formally resolved
by the **Caption Identity Corrective Gate**, commit `875fb04`. Root cause was diagnosed
in hybrid state transition timing and multi-frame consensus disambiguation in
`hybrid_evidence_job.py` and `caption_identity_verification.py`. Formal product fixes
were integrated and verified across 843 passing tests. Subsequently, M11 completed
P2 recognition-only, P3 Windows DirectML recognizer, and P4B Windows DirectML text detector
acceleration, while parallel chunking was evaluated via evidence gate and formally rejected).*


---

## Explicitly not populated

No entry exists for a purely theoretical failure mode with no real
evidence behind it. In particular:

- No entry for "multilingual layer assignment silently produces wrong
  text on real material *at scale*" — see #5's 2026-09-02 update: one
  real miss and two real non-misses have now been observed (n=3 matched
  real bilingual instants), enough to say the failure mode is real, not
  enough to characterize a rate. Still an evidence gap, now a narrower
  one, not a closed question either way.
- No entry for Path A OCR accuracy failures on real (non-benchmark)
  video *under the shipped `PRODUCTION_TRIGGER` profile* — the three
  real bilingual windows that ran it (`docs/m11_representative_evaluation.md`
  §15) were each too timeout-limited (2.2%–3.5% window coverage) to match
  more than one verified instant apiece, too little to call a finding
  either way. `EXPERIMENTAL_HYBRID` DID complete at full coverage on
  three windows and DID surface a real accuracy finding — see #12. The
  representative-video acceptance item remains open, not closed, per the
  section below.

## Representative-video acceptance item: transferred to Milestone 11, not waived

Per `docs/m10_evidence_inventory.md`, `docs/m10_private_corpus_incident.md`,
and ROADMAP.md §17's gate audit disposition (2026-08-31), ROADMAP §17's
3–5 representative videos × 2–5 minute segments target is **not closed**
by any evidence in this report. The controlled/synthetic corpus
underlying findings #7–#9 closes only the reproducible
performance-diagnosis seam. M10's gate audit accepted M10 as complete
while explicitly **transferring this target to Milestone 11 as a
mandatory acceptance gate** (ROADMAP.md §18's acceptance gate 9) — it is
not waived, silently downgraded to optional debt, or treated as
satisfied by any finding above.

**Updated 2026-09-02:** M11 stage 5 has since run real evidence against
this gate — a five-window split-profile stress run (all five windows
`partial_timeout`, findings #5, #7 above) and a completion supplement
that finished three of those windows to full coverage (finding #12
above). This is real progress on the gate, not closure of it: two of the
five frozen windows are fully evaluated, three remain timeout-limited to
under 4% coverage, and the two that finished surfaced a correctness
question (subsequently resolved via Caption Identity Corrective Gate).
Full detail: `docs/m11_representative_evaluation.md` §15–§16. Per the same gate audit
disposition, Milestone 12 must not begin until Milestone 11 completes
the transferred evaluation and its results — whatever they finally are —
are folded back into `EVALUATION_REPORT.md` and this report, which this
update does for the results produced so far.

