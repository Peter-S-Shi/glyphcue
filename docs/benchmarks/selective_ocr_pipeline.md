# Selective OCR Evidence Pipeline Verification — Milestone 4

Real-execution verification that the selective OCR pipeline (ROADMAP.md §11) performs materially fewer OCR calls than a naive dense-OCR baseline on a representative fixture, using the real V1 default OCR runtime (**PaddleOCR**, see `docs/adr/0001-ocr-runtime-selection.md`) — not `FakeOcrEngine`. `FakeOcrEngine`-based tests (`tests/application/test_ocr_evidence_job.py`) already prove the pipeline logic deterministically in CI; this is the separate, real-runtime confirmation that the same logic holds with actual OCR inference and actual timing.

## Environment

- OS: Windows 11 Home (build 10.0.26200)
- Python: 3.12.10 (CPython, 64-bit) — matches V1's target
- Package versions: `paddleocr==3.7.0`, `paddlepaddle==3.3.1` (the exact pair pinned in `pyproject.toml`'s `[ocr]` extra, per `docs/adr/0001-ocr-runtime-selection.md`)
- CPU-only, same developer workstation used for the Milestone 3 OCR runtime benchmark
- Script: `benchmarks/selective_ocr_pipeline/run_verification.py` (not run in CI — requires the optional `[ocr]` extra; run manually to reproduce)
- Raw results: `benchmarks/selective_ocr_pipeline/verification_results.json`

## Fixture

A generated, copyright-safe 4-second synthetic video (`benchmarks/selective_ocr_pipeline/fixture.py`), 40 frames at 100ms spacing, rendered in-script from known text via a Windows system font — no scraped video or real subtitle screenshot:

| Segment | Text |
|---|---|
| 0.0–1.5s | "The quick brown fox" |
| 1.5–3.0s | "jumps over the lazy dog" |
| 3.0–4.0s | (blank — subtitle cleared) |

This models the realistic pattern selective OCR is meant to exploit: long static stretches (subtitle text held on screen) punctuated by real state changes.

## Method

`build_ocr_evidence_job` (`src/glyphcue/application/ocr_evidence_job.py`) was run twice over the identical fixture and a real `PaddleOcrEngine`, differing only in `policy`:

- **selective**: default `ChangeTriggeredOcrPolicy` (frame-difference gated, ROADMAP's "cheap visual analysis")
- **dense**: `NaiveDenseOcrPolicy` (OCRs every analyzed frame — a naive dense-OCR baseline used only as a control, never a production default)

All numbers below are `PipelineMetrics` fields filled in during the real job execution — no estimation or fabricated telemetry.

## Results

| Metric | Selective | Dense (naive baseline) |
|---|---|---|
| Frames analyzed | 40 | 40 |
| **OCR calls** | **3** | **40** |
| Observations created | 2 | 30 |
| Elapsed wall-clock time | 13.64 s | 101.27 s |
| OCR calls / minute | 13.2 | 23.7 |
| Effective processing speed (media s / wall s) | 0.286 | 0.039 |

**OCR call reduction: 92.5%** (3 vs. 40 calls) on this fixture.

Selective OCR's 3 calls are exactly what the fixture's real content justifies: one baseline call at the first frame, one triggered by the real text change at 1.5s, and one triggered by the change to blank at 3.0s (that third call correctly recognized no text, so it produced 0 Observations — the pipeline does not fabricate evidence when there is none). The 2 observations it did produce are:

```text
"The quick brown fox"
"jumps over the lazy dog"
```

— an exact match to the fixture's real ground-truth text, recovered with 13x fewer OCR calls than dense (3 vs 40) and roughly 7.4x less wall-clock time (13.6s vs 101.3s), while dense OCR's 40 calls did not surface any text the selective run missed.

## What this confirms (and doesn't)

- Confirms ROADMAP M4 acceptance gate 3 ("selective OCR performs materially fewer OCR calls than naive dense OCR on representative fixture(s)") with a real OCR engine, not just `FakeOcrEngine`.
- Confirms the pipeline's cheap frame-difference gate (`frame_difference_score`, a commodity mean-absolute-pixel-difference technique — no novelty claim made, per gate 8) is sufficient to catch this fixture's real subtitle transitions without missing them.
- Does **not** claim these absolute latency/throughput numbers are representative of end-user hardware, or that this one fixture proves the change-detection threshold is optimal for all real-world footage (fast fades, noisy compression artifacts, or very brief captions could need different tuning) — that kind of broad calibration is out of scope for this milestone and would need a larger, more varied evidence set.
