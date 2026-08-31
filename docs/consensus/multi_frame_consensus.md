# Multi-Frame Consensus & Cue Reconstruction — Milestone 5

This document answers ROADMAP.md §12's explainability requirement: what the consensus algorithm is, why it was chosen, what alternatives exist, where it fails, and what evidence supports the choice.

## What the algorithm is

`reconstruct_cues_with_consensus` (`src/glyphcue/application/consensus_reconstruction.py`) is a from-scratch Path A seam, deliberately independent of Milestone 1's Path B `reconstruct_cues` (`src/glyphcue/application/reconstruction.py`) — Path B merges complete, clean subtitle-file lines by rolling character-overlap continuation; Path A merges sparse, occasionally-noisy OCR samples of the *same* on-screen state. Reusing one algorithm for both would have forced Path B's continuation heuristic (temporal overlap + text overlap between *different* lines) onto a problem that is actually about *voting among repeated, possibly-wrong readings of one line* — a different problem, so it gets a different, purpose-built algorithm.

Four steps, in order:

1. **Sort** the input Observations by `start_time` (source-correct PTS). The function is called with exactly one evidence run's Observations (see "Input contract" below) — never a mix of runs.
2. **Group into state runs** (`_group_into_state_runs`): walk the sorted list once; consecutive observations join the same run when `character_similarity(previous.text, next.text) >= similarity_threshold` (default `0.5`). A drop below threshold starts a new run — a real state change. `character_similarity` is `1 - normalized Levenshtein distance`, the same formula Milestone 3's CER benchmark uses, just expressed as similarity — plain character-by-character comparison, no whitespace tokenization, so it behaves identically on English, Chinese, and Japanese text with no special-casing.
3. **Vote within each run** (`_consensus_value`): majority vote by exact text match. Ties are broken by the tied candidate's highest-confidence observation, then by earliest occurrence — deterministic, no randomness. Every observation in the run (winning text or not) is kept in `LanguageLayer.observation_ids`, so a reviewer can see exactly what was compared, not just what won.
4. **Time the Cue from state-transition evidence, not frame math**: a Cue's `end_time` is the *next* run's first observation's `start_time` — the moment the next state was confirmed is the real evidence for when this state stopped being shown, which is almost always later (and more honest) than this run's own last sample. Only the final run (no known next state) falls back to its own last observation's `end_time`. This directly avoids the `timestamp = frame_index / fps` anti-pattern the codebase has guarded against since Milestone 2's PTS-correctness tests — here the guard is "don't assume duration ends at the last *sample*," the temporal analogue of "don't assume timestamps come from frame count."

## Input contract

`reconstruct_cues_for_evidence_run` (`src/glyphcue/application/evidence_run_reconstruction.py`) is the only place M5 code calls `ObservationRepository`, and it calls `list_for_run(evidence_run_id)` — never `list_all()`. This is a hard requirement, not a convenience: Observations from two different videos, or two re-runs of the same video, must never be silently merged into one reconstruction (`tests/application/test_evidence_run_reconstruction.py::test_never_aggregates_across_evidence_run_ids` proves this). `reconstruct_cues_with_consensus` itself stays a pure `list[Observation] -> (list[Cue], list[ConsensusDiagnostics])` function with no run-id parameter — the run-scoping responsibility belongs one layer up, at the fetch, matching the existing `evidence_run_id` design from Milestone 4.

## Why this baseline, and not something else

ROADMAP M5 scope is explicit: *"Start with a simple explainable baseline. Do not jump directly to opaque complexity."* Majority-vote-by-exact-text is about as simple as multi-sample text consensus gets — no ML model, no learned weights, no external dependency. It is also directly explainable on a whiteboard: "count how many times each exact reading occurred; the most common one wins; ties go to whichever reading the engine was most confident about."

**Alternatives considered, not built (yet):**

- **Character-position voting** (align all readings and vote per character position, like a multiple-sequence alignment) — strictly more powerful than exact-text voting (could recover a *correct* reading that no single sample got completely right), but is meaningfully more complex to implement and explain, and alignment itself is nontrivial for CJK text where a single missing/extra character shifts every following position. Not built because the evidence below doesn't yet show exact-text voting is insufficient in the *realistic* case — see Evidence.
- **Confidence-weighted voting** (weight each vote by the engine's reported confidence instead of counting occurrences equally) — rejected for V1 because `OcrRuntimeInfo`/`OcrTextRegion.confidence` values are not currently validated to be well-calibrated across engines (per the Milestone 3 ADR, confidence is an engine-reported score, not something GlyphCue has independently benchmarked for calibration); using it as the *primary* signal risks trusting a wrong-but-confident reading over a right-but-modest one. It is used only as a *tie-breaker*, where its risk is smallest.
- **Timing-overlap continuation** (reuse Path B's `_continues_run` timing-overlap check) — rejected because M4's OCR calls are selective and sparse (not a dense frame stream), so consecutive Observations in the list are already temporally adjacent by construction; a timing-overlap test would add complexity without adding information Path A doesn't already have from list order.

## Failure modes (recorded, not hidden)

Two real scenarios were run through the actual production algorithm and a real PaddleOCR engine (`benchmarks/multi_frame_consensus/`, results in `evaluation_results.json`) — full numbers under Evidence below.

1. **Where it helps**: when most readings of a real state agree exactly and one is an outlier (e.g. a single degraded frame among several clean confirmations), majority vote correctly discards the outlier. Real evidence: English and Chinese lines both improved from a single wrong/truncated first reading (CER 0.045 / 0.111) to an exact match (CER 0.0) once 4 clean confirmations outvoted it.
2. **Where it does not help (and can get worse)**: when *every* reading is independently degraded enough that no two are exactly equal, the vote degenerates to a 5-way tie, and the algorithm falls back to the highest-confidence reading — which is not guaranteed to be the most *correct* one. Real evidence: in the "all 5 heavily degraded" scenario, consensus CER (0.153 mean) was measurably *worse* than the single-frame baseline (0.052 mean) for the English and Japanese lines, because the confidence-based tie-break picked a more badly-truncated reading than the naive first-frame pick happened to be.

This second case is the concrete, measured argument for *not* building character-position voting or confidence-weighted voting speculatively right now: the failure only shows up under near-worst-case degradation (every single sample corrupted differently), which is not what M4's `ChangeTriggeredOcrPolicy` actually produces in normal operation (it OCRs on detected change or periodic confirmation of an already-stable state, so most of a state's readings are ordinary, not independently-degraded). If future evidence from real-world footage shows this failure mode is common rather than a constructed worst case, character-position voting is the documented next step — not before.

3. **A related, honestly-scoped limitation, not yet evidenced either way**: M4 does not emit an Observation for a "no subtitle visible" state (empty OCR text is dropped, not persisted). This means the current baseline has no direct signal for "the subtitle actually disappeared here" versus "no new OCR call happened to run here" — it always treats the next run's start as this run's end, even across what might really be a blank gap. No real evidence has been gathered yet on how often this matters in practice; it's recorded here as a known simplification rather than silently assumed away.

## Evaluation corpus

Three ground-truth lines (English, Chinese, Japanese), rendered in-script from known text via Windows system fonts (`benchmarks/multi_frame_consensus/fixture.py`) — no scraped video frame or real subtitle screenshot, matching the same copyright-safety approach as the Milestone 3/4 benchmark corpora. Each line gets 5 independently-degraded image variants (blur + contrast + additive noise + a randomly-positioned occlusion patch for the "heavy" degradation level), run through the real, pinned `PaddleOcrEngine` (`paddleocr==3.7.0`/`paddlepaddle==3.3.1`).

Two scenarios per line:

- **`mixed_4_clean_1_degraded`**: 1 heavily-degraded read (placed first, simulating a bad reading right as a change is detected) + 4 mildly-blurred, otherwise clean reads (simulating settled confirmation frames) — the realistic case.
- **`all_5_heavily_degraded`**: all 5 reads heavily degraded independently — the deliberate worst case, to honestly find where the baseline stops helping.

## Evidence (real PaddleOCR, real algorithm, no fabricated numbers)

| Scenario | Language | Single-frame CER | Consensus CER | Change |
|---|---|---|---|---|
| mixed (realistic) | English | 0.0455 | 0.0 | **improved** |
| mixed (realistic) | Chinese | 0.1111 | 0.0 | **improved** |
| mixed (realistic) | Japanese | 0.0 | 0.0 | no change (already correct) |
| **mixed mean** | | **0.0522** | **0.0** | **-0.0522** |
| all-noisy (worst case) | English | 0.0455 | 0.2045 | **worse** |
| all-noisy (worst case) | Chinese | 0.1111 | 0.1111 | no change |
| all-noisy (worst case) | Japanese | 0.0 | 0.1429 | **worse** |
| **all-noisy mean** | | **0.0522** | **0.1528** | **+0.1006** |

Raw per-item readings, texts, and CER values: `benchmarks/multi_frame_consensus/evaluation_results.json`. Deterministic unit-level proof of the same mechanics (majority vote over a noisy outlier, confidence tie-break, CJK grouping/voting without whitespace tokenization): `tests/application/test_consensus_reconstruction.py`.

## Conclusion

The simple majority-vote baseline is the right V1 choice: it measurably helps in the realistic scenario M4's selective-OCR pipeline actually produces, it is fully whiteboard-explainable, and its one measured failure mode is confined to a worst-case scenario that doesn't reflect normal `ChangeTriggeredOcrPolicy` behavior. Per ROADMAP's explicit instruction, added complexity (character-position voting, confidence-weighted voting) is deferred until real-world evidence — not a constructed worst case — shows it's needed.
