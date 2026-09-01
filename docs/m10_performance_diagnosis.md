# Milestone 10 — Performance Diagnosis (Path A, Real OCR, Isolated Measurements)

Produced in response to the private-corpus crash (`docs/m10_private_corpus_incident.md`),
which mixed a real evaluation-harness bug with a real product-performance
question in one confounded ~40-minute number. This document isolates each
real cost separately, on small controlled/synthetic fixtures
(`benchmarks/m10_controlled_video_corpus/`), using the real, unmodified
production seams throughout (`PaddleOcrEngine`, `build_ocr_evidence_job`
/ `build_multilingual_ocr_evidence_job`, `ChangeTriggeredOcrPolicy`,
`NaiveDenseOcrPolicy`) — nothing here is estimated or guessed from the
crashed run's total alone. Raw results:
`benchmarks/m10_controlled_video_corpus/performance_diagnosis_results.json`.

**No optimization is implemented in this document or its commit.** Per
the repo owner's explicit instruction, production scalability/hardening
work is routed to Milestone 11; the one change made here
(`benchmarks/private_video_corpus/run_evaluation.py`'s cancel-on-timeout
and connection-close fixes) is an evaluation-harness bug fix, not a
production optimization.

## Observed bottleneck: OCR-call latency, by a wide margin

| Stage | Measurement | Evidence |
|---|---|---|
| Pure frame decode (PyAV, no OCR) | 171–358 frames/sec | `pure_decode.frames_per_second`, all 3 fixtures |
| Real `PaddleOcrEngine.recognize()` call, single call, tiny (480×160) crop | mean 2.9–3.3s, median 2.2–3.6s, p95 3.7–6.4s | `ocr_call_latency`, all 3 fixtures |
| `PaddleOcrEngine` construction (`initialize()`) | 1.6–3.4s, one-time per engine | `engine_construction_seconds` |
| Persisting 1000 synthetic `Observation`s | 143–147 observations/sec (≈7ms each) | `persistence_1000_observations` |
| Real reconstruction (`reconstruct_cues_with_consensus` / multilingual) | not separately timed here — always completed instantly relative to OCR; not a measurable contributor at this scale | selective/dense run wall-clock ≈ (engine construction) + (OCR calls × latency), no unaccounted remainder |
| Harness waiting/event-loop overhead (outer script wall time − job's own `elapsed_seconds`) | -0.008s to +0.010s across all 6 real job runs | `harness_waiting_overhead_seconds` in every run entry |

**Decode is not the bottleneck** (over 170 fps even on an unoptimized pure-Python loop). **Persistence is not the bottleneck** (7ms/row is negligible at the observation counts these jobs produce). **The harness's own event-loop/signal-dispatch overhead is not a bottleneck** (sub-10-millisecond in every measured run — Qt signal/thread-join overhead is not where the time goes). **A single real PaddleOCR call, even on a tiny crop, costs ~3 seconds** — this is the dominant, structural cost, consistent with ADR 0001's original per-item latency numbers (2.3–3.3s) carrying straight through to this isolated measurement.

## Consequence: even the best case is slower than realtime

The **selective** policy (production default) on these small, mostly-static fixtures still ran slower than realtime:

| Fixture | Real OCR calls (selective) | Media processed | Wall clock | Ratio (wall/media) |
|---|---|---|---|---|
| clean_single_language | 3 | 5.90s | 11.72s | **1.99×** realtime |
| bilingual_typical | 8 (2 languages × ~4 triggers) | 5.90s | 38.02s | **6.44×** realtime |
| difficult_noisy_background | 3 | 5.90s | 11.34s | **1.92×** realtime |

Roughly 30–40% of each selective run's wall time on these 6-second clips is the one-time engine-construction cost (1.6–3.4s) — a fixed cost that matters proportionally more on short clips and less on longer real videos, but the remaining, dominant cost is still N real OCR calls × ~3s/call.

The **dense** policy (OCR every analyzed frame — never a production default, used here only as a control, per ADR 0002) confirms the mechanism directly: it was still cancelled by the 60-second per-run timeout having processed only 1.5s of media (clean/noisy — **40.6×/40.8× realtime**) or 0.4s of media (bilingual, 2× the calls per frame — **166.4× realtime**). This is the same shape of collapse the private-corpus crash showed, reproduced here cleanly and without the harness's concurrency bug confounding it.

## Connecting this back to the private-corpus incident

`private-a-clean-zh`'s real trigger count (177 triggers over ~17.5 real media-seconds) is a meaningfully higher trigger *rate* than these controlled fixtures' 3–8 triggers over 5.9s — consistent with `ChangeTriggeredOcrPolicy`'s change-detection threshold firing far more often on a real, non-static camera background than on a clean synthetic fixture. Given ~3s/call is the structural cost regardless of what triggered it, a real video whose background pushes the trigger rate toward dense-like frequency will show dense-like (tens-to-hundreds-of-times realtime) wall-clock cost — exactly what the crashed run's partial data is consistent with, independent of the harness's concurrency bug making the absolute number worse still.

**Negative result, reported honestly:** this document's `difficult_noisy_background` fixture (independent per-frame random pixel noise added to an otherwise-static background) was built specifically to try to reproduce that elevated trigger rate in a controlled way — and did **not** reproduce it: it triggered exactly 3 times, identical to the clean fixture. The likely reason: `ChangeTriggeredOcrPolicy`'s frame-difference gate is presumably a mean-based score (per ADR 0002, "a commodity mean-absolute-pixel-difference technique"), and independent, zero-mean random noise across a whole ROI averages out to a small mean delta that doesn't cross the trigger threshold — whereas a real camera's background motion (a person's hands/body moving, a gradual lighting drift) is spatially *correlated*, not independent per-pixel noise, and would plausibly produce a materially larger mean delta. This is recorded as a genuine miss for this specific reproduction attempt, not silently fixed by picking a different noise fixture until the numbers matched — a real fixture using structured motion (e.g. a slowly panning or drifting background) is the honest next step if this needs closer reproduction, not attempted here.

## Ranked candidate improvements (M11 scope — not implemented here)

Ranked by expected gain × implementation risk, given the evidence above that OCR-call cost (not decode, persistence, reconstruction, or harness overhead) is the lever that matters:

1. **Lower unnecessary OCR-call frequency without changing reconstruction quality** (highest expected gain, lowest risk). Since cost is ~linear in call count and calls are the bottleneck by a wide margin, reducing real-world trigger rate (recalibrating `ChangeTriggeredOcrPolicy`'s threshold against real, non-static footage — the exact gap ADR 0002 already flagged as unverified) has the most direct, proportional payoff of anything on this list, and changes no reconstruction logic at all.
2. **ROI size / downscale before OCR** (high expected gain, low-moderate risk). PaddleOCR's own latency scales with input resolution; the real corpus's ROI crops were larger than this document's tiny 480×160 test crops. A smaller/downscaled ROI, or capping analysis resolution before the OCR call, directly attacks the ~3s/call cost without touching trigger logic. Risk: must be verified against ADR 0001's CER evidence to confirm downscaling doesn't reintroduce the accuracy loss that benchmark already ruled out for the chosen runtime.
3. **Runtime/model reuse across languages** (moderate gain, low risk). Multilingual jobs pay the ~3s/call cost once per language per triggered frame (bilingual's 8 calls vs. clean's 3, for a comparable number of real triggers); if the underlying model backend can share a warmed session across language configurations more cheaply than fresh per-language calls, this is a real, bounded win — needs verification against ADR 0001's own note that PaddleOCR loads a separate model per `lang=` value.
4. **Progress/ETA telemetry in production, not just evaluation** (moderate value, low risk, cheap to build). `Job.progress` already exists and is already emitted by both evidence jobs; nothing production-side needs to change — only a real UI/CLI consumer needs to subscribe, mirroring the fix already made to the evaluation harness in this same commit.
5. **Bounded sample/chunk parallelism** (moderate gain, higher risk). Running independent chunks of one video (or independent videos) concurrently could reduce wall-clock time on multi-core hardware, but real GIL/CPU contention was directly observed in the crashed run (b/c starved while a's orphaned thread ran) — any parallelism must be a deliberate, bounded worker pool with real concurrency testing, not the accidental unbounded concurrency the harness bug produced. Higher risk because it changes production job-orchestration, not just evaluation code.
6. **Adaptive logical chunking with overlap and deterministic reconciliation** (real potential, highest risk/complexity). Would let a long video be processed as several shorter, resumable/fault-isolated ranges with boundary reconciliation — directly useful for both parallelism (4) and fault isolation (a crash mid-video wouldn't lose all prior progress, unlike this incident). Not attempted here: this is a real architecture change to Path A's job model, squarely M11 (Product Hardening) territory, and the M10 prompt explicitly forbids production behavior changes under Feature Freeze.
7. **Resumable/fault-isolated chunks** — same M11 scope note as (6); listed separately because it could in principle be built independent of parallelism (e.g. checkpointing progress within a single-threaded run), but the real value is realized together with (6).

Items 1–2 are the recommended M11 starting point given the evidence above: they attack the dominant, clearly-isolated cost (OCR-call count and per-call latency) directly, without the architectural risk of 5–7.
