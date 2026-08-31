# ADR 0001: OCR Runtime Selection for V1

**Status:** Accepted
**Date:** 2026-08-31
**Milestone:** ROADMAP.md Milestone 3 — OCR Adapter & Runtime Selection

## Context

GlyphCue needs a CPU-first OCR runtime for Path A (burned-in subtitle reconstruction). The product architecture requires reliable multilingual/CJK support — Chinese and Japanese recognition are not optional edge cases, they are a stated first-class differentiator (see `GLYPHCUE_PRODUCT_ARCHITECTURE.md`, and the CJK-aware requirements running through Milestones 5, 6, and 8 of `ROADMAP.md`).

ROADMAP.md §10 named exactly two initial candidates to benchmark: **RapidOCR** (ONNX Runtime backend) and **PaddleOCR** (PaddlePaddle backend). Full methodology, corpus, and raw numbers are in `docs/benchmarks/ocr_runtime_selection.md`; this ADR states the decision and its rationale.

## Chosen runtime

**PaddleOCR**, wrapped behind the frozen `OcrEngine` contract as `glyphcue.adapters.paddleocr_engine.PaddleOcrEngine`.

## Why

The benchmark corpus deliberately included Chinese, Japanese, a bilingual crop, a low-quality crop, and a styled subtitle crop — not just English — because GlyphCue's core value is reconstructing *difficult*, often multilingual, burned-in captions.

- **PaddleOCR scored a perfect CER (0.0) on all 6 corpus items**, including Japanese and the degraded low-quality crop.
- **RapidOCR failed Japanese outright** (CER 0.6429 — it dropped most of the hiragana in the ground truth). This is because `rapidocr_onnxruntime`'s default installable package bundles only one recognition model (`ch_PP-OCRv4_rec_infer.onnx`, a Chinese+English combo) and ships no Japanese-specific model. Since Japanese is an explicit product requirement, this is disqualifying as a default, not a minor accuracy gap to accept.

Correctness on the product's stated differentiator outweighs PaddleOCR's real cost disadvantages (see "What was rejected" below): a smaller, faster runtime that cannot read Japanese text is not a usable V1 default for GlyphCue.

PaddleOCR's steady-state per-item latency was also lower than RapidOCR's once warmed (0.80–1.04s vs 1.15–1.38s in this environment, re-verified on Windows Python 3.12 with a corrected per-language warm-up methodology — see `docs/benchmarks/ocr_runtime_selection.md`), so the correctness win is not purchased with a universal performance loss — only with startup time and footprint (below).

## What was rejected, and why it was still close

**RapidOCR** was not rejected because it is a bad library — for English/Chinese-only use cases it would be an excellent, much lighter choice:

- ~212 MB total footprint vs PaddleOCR's ~590 MB (packages + downloaded models).
- ~69–114 MB memory footprint vs PaddleOCR's ~389–792 MB.
- 1.6s startup vs PaddleOCR's 4.0s.
- Zero API/compatibility issues encountered, vs PaddleOCR's real crash (below).

If a future evidence-based need arises for a lighter-weight or English/Chinese-only deployment mode, RapidOCR remains a legitimate second implementation of the same `OcrEngine` contract — see "What remains swappable."

## Known cost of the choice (accepted, not ignored)

- **A real crash was hit and worked around.** `PaddleOCR(...)` with its default `enable_mkldnn=True` raised `NotImplementedError: (Unimplemented) ConvertPirAttribute2RuntimeAttribute not support [pir::ArrayAttribute<pir::DoubleAttribute>]` on this CPU, with `paddleocr==3.7.0` / `paddlepaddle==3.3.1`. The fix, `enable_mkldnn=False`, is baked into `PaddleOcrEngine`'s construction (`glyphcue/adapters/paddleocr_engine.py`) and documented there and in the benchmark report. This is a real, version-pairing-specific bug, not a corpus artifact — it must be re-verified whenever `paddleocr`/`paddlepaddle` versions are upgraded.
- **Larger footprint.** ~590 MB on disk (packages + auto-downloaded models) vs RapidOCR's ~212 MB, and 5–7x the memory footprint depending on how many languages are loaded simultaneously.
- **Slower startup.** 4.0s vs RapidOCR's 1.6s for engine construction.
- **Per-language model loads.** PaddleOCR loads a separate model per `lang=` value (en/ch/japan were all exercised); memory scales with the number of simultaneously active languages, unlike RapidOCR's single combined model.
- **Heavy default pipeline.** `PaddleOCR()` with no explicit flags loads document-preprocessing stages (orientation classification, dewarping) irrelevant to small subtitle crops; `PaddleOcrEngine` explicitly disables these (`use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False`) to keep it appropriate for GlyphCue's actual use case.

## What remains swappable

Nothing about this decision is hard-wired past the `OcrEngine` boundary:

- `glyphcue.adapters.ocr_engine.OcrEngine` is the frozen, GlyphCue-owned contract (`initialize`, `recognize`, `supported_languages`, `runtime_info`, `shutdown`, all vendor-exception-normalized). Application/domain code depends only on this Protocol and on `OcrTextRegion`/`OcrRuntimeInfo`/`OcrError` (`glyphcue/adapters/ocr_types.py`) — never on `paddleocr`, `paddlex`, or `paddle` types directly (enforced by `tests/adapters/test_boundaries.py`'s static import scan). `OcrTextRegion.geometry` and `OcrRuntimeInfo.backend_version` were added as optional fields in a Milestone 3 corrective pass (both default to `None`, so no existing caller breaks); `PaddleOcrEngine` populates geometry from PaddleOCR's `rec_polys` and only ever accepts/reports GlyphCue's canonical `en`/`zh`/`ja` codes — PaddleOCR's own `ch`/`japan` vendor codes are mapped internally and never cross the boundary in either direction (constructing `PaddleOcrEngine` with a non-canonical code raises `ValueError`).
- `tests/support/fake_ocr_engine.FakeOcrEngine` proves application/test code can fully exercise OCR-dependent logic without either real runtime installed.
- A future `RapidOcrEngine` (or any other `OcrEngine` implementation) can be dropped in wherever `PaddleOcrEngine` is used today with no change to calling code, and could legitimately be offered as a lighter-weight configuration option later if real product evidence (e.g. an English/Chinese-only deployment target, or a fixed PaddleOCR compatibility issue that regresses) justifies it. That decision is explicitly deferred, not foreclosed.

## Windows standalone packaging implications

V1 ships as a Windows desktop app (`pyside6-deploy`/Nuitka per `ROADMAP.md` §3). PaddleOCR's ~590 MB footprint (vs RapidOCR's ~212 MB) will materially increase installer size and first-run disk usage — this is a real, accepted cost of the correctness decision above, and should be treated as a known constraint (not a surprise) when Milestone 11 (Product Hardening) resolves Qt plugins, FFmpeg, and OCR model asset bundling for the standalone build. The `enable_mkldnn=False` workaround must also be re-verified against whatever `paddlepaddle` wheel actually gets bundled for Windows, since CPU-backend behavior can differ by build.

## What evidence supported this choice

Full methodology, environment, corpus definition, and raw results: `docs/benchmarks/ocr_runtime_selection.md` and `benchmarks/ocr_runtime_selection/benchmark_results.json`. Summary: a 6-item generated, copyright-safe corpus (English, Chinese, Japanese, bilingual crop, low-quality crop, representative subtitle style) was run against both candidates on the same CPU-only machine in the same session, measuring CER, startup time, steady-state latency (median of 3 warm calls, now genuinely per-language-warm), process RSS before/after model load and at a true running-maximum peak, installed package/model size, and API/error behavior.

**Re-verification note (Milestone 3 corrective pass):** the benchmark was re-run in full on Windows Python 3.12.10 — the interpreter version V1 actually targets — after fixing two measurement bugs: a missing per-language warm-up call (which had folded first-call JIT/session-setup cost into PaddleOCR's Chinese/Japanese "steady-state" latency) and a mislabeled single post-run RSS snapshot reported as "peak memory" (now a genuine running maximum). The CER results and the runtime decision are unaffected by this correction — PaddleOCR still scores 0.0 on all 6 items and RapidOCR still fails Japanese (CER 0.6429). Absolute latency numbers changed materially (both engines measured faster once the warm-up bug was fixed); see `docs/benchmarks/ocr_runtime_selection.md` for the corrected figures. The `paddleocr`/`paddlepaddle` version pair was independently re-resolved on Python 3.12 rather than assumed from the earlier Python 3.11 run, and is now pinned exactly (not `>=`) in `pyproject.toml`'s `[ocr]` extra to prevent future installs from silently drifting onto an unverified pair.
