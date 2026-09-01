# ADR 0002: Selective (Change-Triggered) OCR Strategy for Path A

**Status:** Accepted
**Date:** 2026-08-31 (Milestone 10 ADR closure; decision and evidence originate from Milestone 4)
**Milestone:** ROADMAP.md Milestone 4 — Selective OCR Evidence Pipeline

## Context

Path A must turn a video into OCR evidence without OCR-ing every analyzed frame: OCR inference is the most expensive step in the pipeline (see ADR 0001's PaddleOCR latency numbers), and a burned-in subtitle typically holds the same on-screen state for many consecutive frames. Running OCR on every frame would be correct but wasteful — most calls would just re-read text already captured.

This ADR states the decision; the full methodology, fixture, and raw numbers are in `docs/benchmarks/selective_ocr_pipeline.md` and `benchmarks/selective_ocr_pipeline/verification_results.json` — not duplicated here.

## Chosen strategy

**`ChangeTriggeredOcrPolicy`**: a cheap, real-time frame-difference gate (`frame_difference_score`, a commodity mean-absolute-pixel-difference technique — no novelty claimed) decides which frames get OCR'd. A frame is OCR'd when it is the first frame, when the gate detects a visual change since the last OCR'd frame, or on a periodic confirmation interval (so a long static state doesn't silently drift out of evidence forever). `NaiveDenseOcrPolicy` (OCR every analyzed frame) exists only as an evaluation control baseline, never as a production default.

## Why

Real-execution verification (`benchmarks/selective_ocr_pipeline/run_verification.py`, real `PaddleOcrEngine`, not `FakeOcrEngine`) on a 40-frame generated fixture with two real text segments and a blank tail showed:

| Metric | Selective | Dense (naive baseline) |
|---|---|---|
| OCR calls | 3 | 40 |
| Observations created | 2 (exact match to ground truth) | 30 |
| Elapsed wall-clock time | 13.64s | 101.27s |

**92.5% OCR-call reduction**, with the selective run's 2 observations exactly matching the fixture's ground-truth text — dense OCR's 37 additional calls surfaced no text the selective run missed. The 3 selective calls are exactly what the fixture's real content justifies: the first frame, the real change at 1.5s, and the real change to blank at 3.0s.

Comparing against dense OCR (an already-available, zero-extra-engineering baseline the architecture naturally provides, per ROADMAP.md section 17's preference for baselines the system already has) rather than an artificially weakened strawman is what makes this comparison meaningful.

## What was rejected, and why

**Dense OCR** was never a real candidate for production use — it is the control baseline this ADR's evidence is measured against, not a competing design. It remains useful as exactly that: a correctness/coverage check that selective OCR isn't silently missing real text changes.

## Known cost of the choice (accepted, not ignored)

- **Change-detection is a candidate, not proof.** `frame_difference_score` crossing its threshold means *something* changed visually — a moving background behind static burned-in text, or a compression artifact, can trigger it without the subtitle text itself changing. This is why M5's consensus reconstruction (ADR 0003) treats `state_trigger` as candidate evidence requiring confirmation from the next real reading, not a confirmed fact on its own — the two milestones' designs are coupled on this point.
- **No broad calibration claim.** This verification uses one fixture with clean, well-separated transitions. It does not claim the change-detection threshold is optimal for fast fades, noisy compression artifacts, or very brief captions — that would need a larger, more varied evidence set, explicitly out of Milestone 4's scope.

## What remains swappable

`ChangeTriggeredOcrPolicy` and `NaiveDenseOcrPolicy` are both concrete implementations behind `build_ocr_evidence_job`'s `policy` parameter (`src/glyphcue/application/ocr_evidence_job.py`) — a different gating strategy (e.g. a learned change detector) could be substituted without changing the OCR evidence job's own contract, if future evidence showed the current threshold-based gate was insufficient for some real-world material class.

## What evidence supported this choice

Full methodology, fixture definition, and raw results: `docs/benchmarks/selective_ocr_pipeline.md` and `benchmarks/selective_ocr_pipeline/verification_results.json`.
