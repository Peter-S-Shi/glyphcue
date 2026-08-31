# ADR 0003: Multi-Frame Consensus Reconstruction Approach for Path A

**Status:** Accepted
**Date:** 2026-08-31 (Milestone 10 ADR closure; decision and evidence originate from Milestone 5)
**Milestone:** ROADMAP.md Milestone 5 — Multi-Frame Consensus & Cue Reconstruction

## Context

Path A's selective OCR pipeline (ADR 0002) produces sparse, occasionally-noisy OCR readings of the same on-screen subtitle state. Path A needs to turn that evidence into Cues: deciding where one subtitle state ends and the next begins, and what the winning text/language is when readings disagree. This is a different problem from Path B's (reconstructing complete, already-clean subtitle-file lines by rolling continuation) — reusing Path B's algorithm would force a continuation heuristic built for *different* lines onto a problem that is really about *voting among repeated, possibly-wrong readings of one line*.

This ADR states the decision; the full algorithm walkthrough, failure-mode analysis, and evidence are in `docs/consensus/multi_frame_consensus.md` — not duplicated here.

## Chosen approach

**`reconstruct_cues_with_consensus`** (`src/glyphcue/application/consensus_reconstruction.py`): same-frame region aggregation, then majority-vote-by-exact-text within state runs, with run boundaries backstopped by M4's own change-detection/blank-marker evidence (treated as a *candidate* requiring confirmation from the next real reading, not a confirmed fact — see ADR 0002) rather than derived from text similarity alone.

## Why

ROADMAP M5 scope is explicit: *"Start with a simple explainable baseline. Do not jump directly to opaque complexity."* Majority-vote-by-exact-text is about as simple as multi-sample text consensus gets — no ML model, no learned weights, no external dependency — and is directly whiteboard-explainable: "count how many times each exact reading occurred; the most common one wins; ties go to whichever reading the engine was most confident about."

Real evidence (`benchmarks/multi_frame_consensus/`, real PaddleOCR, real production functions) shows this baseline measurably helps in the realistic case: a mixed scenario (1 degraded + 4 clean readings per line, across English/Chinese/Japanese) improved mean CER from 0.0522 (single-frame) to 0.0 (consensus).

## What was rejected, and why

- **Character-position voting** (align all readings, vote per character position) — strictly more powerful (could recover a correct reading no single sample got fully right), but meaningfully more complex to implement and explain, and alignment is nontrivial for CJK text where one missing/extra character shifts every following position. Not built because the evidence available doesn't show exact-text voting is insufficient in the realistic (non-worst-case) scenario.
- **Confidence-weighted voting** (weight votes by engine-reported confidence) — rejected as the *primary* signal because `OcrTextRegion.confidence` is not independently validated to be well-calibrated across engines (ADR 0001); it is used only as a tie-breaker, where miscalibration risk is smallest.
- **Timing-overlap continuation** (reusing Path B's `_continues_run` check) — rejected because M4's OCR calls are already selective and sparse, so consecutive Observations are already temporally adjacent by list order; a timing-overlap test would add complexity without adding information Path A doesn't already have.

## Known cost of the choice (accepted, not ignored)

**Where it does not help (and can get worse):** when every reading of a state is independently degraded enough that none are exactly equal, the vote degenerates toward a many-way tie. In a deliberately constructed worst-case scenario (all 5 readings heavily degraded, no `state_trigger` evidence at all), mean consensus CER (0.1052) was measurably *worse* than the single-frame baseline (0.0522) for the English item, whose severe degradation caused the OCR engine to fragment one line into multiple detected regions.

This failure is not treated as disqualifying: it only appears under near-worst-case degradation combined with the *absence* of real `state_trigger` evidence, which is not what `ChangeTriggeredOcrPolicy` (ADR 0002) actually produces in normal operation. If real-world footage evidence later shows this failure mode is common rather than a constructed worst case, character-position voting is the documented next step — not built speculatively now.

## What remains swappable

`reconstruct_cues_with_consensus` is a pure `list[Observation] -> (list[Cue], list[ConsensusDiagnostics])` function with no dependency on the OCR engine, the invocation policy, or persistence — a different voting/grouping algorithm could be substituted behind the same signature if future evidence justified it.

## What evidence supported this choice

Full algorithm walkthrough, candidate-evidence-confirmation mechanics, failure-mode analysis, and raw CER numbers: `docs/consensus/multi_frame_consensus.md` and `benchmarks/multi_frame_consensus/evaluation_results.json`.
