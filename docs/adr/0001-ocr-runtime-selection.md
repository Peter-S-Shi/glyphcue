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

PaddleOCR's steady-state per-item latency was also lower than or comparable to RapidOCR's once warmed in every re-run on this machine (most recently 2.34–2.94s vs 2.95–3.12s; per-item latency varies noticeably run-to-run on this developer workstation from ~0.8s to ~3.3s depending on background load, but PaddleOCR's relative advantage and both engines' CER results have stayed stable across every re-run — see `docs/benchmarks/ocr_runtime_selection.md` for the full variance discussion), so the correctness win is not purchased with a universal performance loss — only with startup time and footprint (below).

## What was rejected, and why it was still close

**RapidOCR** was not rejected because it is a bad library — for English/Chinese-only use cases it would be an excellent, much lighter choice:

- ~212 MB total footprint vs PaddleOCR's ~590 MB (packages + downloaded models).
- ~70–116 MB memory footprint (`max_observed_rss_mb`, an approximation -- see benchmark report) vs PaddleOCR's ~368–789 MB.
- 1.55s startup (import + default-language construction, warm-up excluded) vs PaddleOCR's 4.57s.
- Zero API/compatibility issues encountered, vs PaddleOCR's real crash (below).

If a future evidence-based need arises for a lighter-weight or English/Chinese-only deployment mode, RapidOCR remains a legitimate second implementation of the same `OcrEngine` contract — see "What remains swappable."

## Known cost of the choice (accepted, not ignored)

- **A real crash was hit and worked around.** `PaddleOCR(...)` with its default `enable_mkldnn=True` raised `NotImplementedError: (Unimplemented) ConvertPirAttribute2RuntimeAttribute not support [pir::ArrayAttribute<pir::DoubleAttribute>]` on this CPU, with `paddleocr==3.7.0` / `paddlepaddle==3.3.1`. The fix, `enable_mkldnn=False`, is baked into `PaddleOcrEngine`'s construction (`glyphcue/adapters/paddleocr_engine.py`) and documented there and in the benchmark report. This is a real, version-pairing-specific bug, not a corpus artifact — it must be re-verified whenever `paddleocr`/`paddlepaddle` versions are upgraded.
- **Larger footprint.** ~590 MB on disk (packages + auto-downloaded models) vs RapidOCR's ~212 MB, and roughly 5–7x the memory footprint depending on how many languages are loaded simultaneously.
- **Slower startup.** 4.57s vs RapidOCR's 1.55s for engine construction (import + default-language construction only, warm-up excluded from both).
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

Full methodology, environment, corpus definition, and raw results: `docs/benchmarks/ocr_runtime_selection.md` and `benchmarks/ocr_runtime_selection/benchmark_results.json`. Summary: a 6-item generated, copyright-safe corpus (English, Chinese, Japanese, bilingual crop, low-quality crop, representative subtitle style) was run against both candidates on the same CPU-only machine in the same session, measuring CER, startup time (import + default-language construction, warm-up excluded, identically defined for both engines), steady-state latency (median of 3 warm calls, genuinely per-language-warm), process RSS before/after model load and a `max_observed_rss_mb` sampled after every load/warm-up/inference step (an approximation, not a true peak — see the benchmark report), installed package/model size, and API/error behavior.

**Re-verification note (Milestone 3, first corrective pass):** the benchmark was re-run in full on Windows Python 3.12.10 — the interpreter version V1 actually targets — after fixing two measurement bugs: a missing per-language warm-up call (which had folded first-call JIT/session-setup cost into PaddleOCR's Chinese/Japanese "steady-state" latency) and a mislabeled single post-run RSS snapshot then called "peak memory". The `paddleocr`/`paddlepaddle` version pair was independently re-resolved on Python 3.12 rather than assumed from the earlier Python 3.11 run, and is now pinned exactly (not `>=`) in `pyproject.toml`'s `[ocr]` extra to prevent future installs from silently drifting onto an unverified pair.

**Re-verification note (Milestone 3, second corrective pass):** two further wording/methodology issues were fixed and the benchmark re-run again: (1) the RSS running-maximum was still being described as a "true"/"genuine" peak, which overstates what discrete post-step sampling with a pre-sample `gc.collect()` can actually observe — it is now reported as `max_observed_rss_mb` and documented as an approximation that can miss transient in-call spikes; no new memory measurement was needed for this, only the relabeling. (2) `startup_seconds` was asymmetric between the two engines — RapidOCR measured import+construction, but PaddleOCR's measurement window extended past its warm-up call — so both are now defined identically as import+default-language-construction-only, with warm-up excluded from both. Re-running surfaced real, substantial run-to-run latency variance on this developer workstation (per-item latency has ranged from under 1s to over 3s across different re-runs of identical code), which the benchmark report now documents explicitly rather than presenting a single run's numbers as if they were precise or stable. Across every re-run, including this one, the CER results and PaddleOCR's relative latency advantage have stayed consistent — the runtime decision is unaffected by either fix.

## Milestone 11 addendum: opt-in DirectML accelerator (P3)

This ADR rejected RapidOCR as the **default** runtime (above), but explicitly left the door open ("What remains swappable") for a second `OcrEngine`/`RegionOcrEngine` implementation if real evidence justified one. Milestone 11's **initial** P3 gate (private evidence: `private_samples/phase0b/PHASE0B_REPORT.md`, not tracked) measured RapidOCR + ONNX Runtime DirectML (`DmlExecutionProvider`) as a genuine GPU accelerator option and found real upside (fixed-crop recognition-only latency 0.184–0.294s vs Paddle's CPU path) alongside a real, then-unresolved risk: RapidOCR's bundled small recognition model showed non-zero CER against Paddle's zero-CER result on at least one sample, and Chinese/Japanese coverage in that first pass was a single synthetic case each — not enough to support a broad accuracy claim. That initial gate's own conclusion was risk: medium-to-high, priority: medium, opt-in only.

**P3 Confirmation Gate (final, supersedes the initial risk rating above):** the thin-evidence gap was the open item, not a settled defect, and was closed by re-running against 10 harder cases rather than the initial gate's small sample: 8/10 exact matches, and the remaining 2 showed no meaningful business degradation (readable, correctly-timed output, not silent failures). The `g`/`e` entries' Cue-level parity against Paddle was 36/36. Interleaved A/B timing across this expanded set measured a real ~1.7–1.95x end-to-end incremental speedup for the DirectML path. On this evidence, the Confirmation Gate's final verdict is **ACCEPT-AS-WINDOWS-OPT-IN**: the initial gate's medium/high-risk rating was a function of thin ZH/JA evidence, not a fundamental quality problem, and that gap is now closed for this scope — opt-in, non-default, exactly as this addendum ships it.

**What shipped:** `glyphcue.adapters.directml_ocr_engine.DirectMlOcrEngine`, a `RegionOcrEngine` implementation identical in shape to `PaddleOcrEngine`'s P2 recognition-only path — it uses RapidOCR's own public standalone method (`RapidOCR.recognize_txt`, which only calls `self.text_rec`, never `self.text_det`) for `recognize_regions`, and reuses GlyphCue's own `_sort_polygons_in_reading_order`/`_crop_polygon_region` (the same functions `PaddleOcrEngine` uses) rather than any RapidOCR-internal geometry helper. `glyphcue.adapters.ocr_engine_selection.create_ocr_engine(language, prefer_directml=...)` is the only sanctioned construction path: `prefer_directml` defaults to `False` (existing callers are unaffected), and even when a caller opts in, `PaddleOcrEngine` is returned unless a real DirectML initialization probe on this machine succeeds — a missing `[directml]` install, a non-Windows platform, or a genuine provider-initialization failure (e.g. no DX12-capable adapter) all fall back to Paddle, not to a crash. This is reachable from the real product, not just tests: `glyphcue.ui.app.create_path_a_app` wires `ocr_engine_factory` to a small function reading the `GLYPHCUE_PREFER_DIRECTML_OCR` env var (unset/anything but `"1"` keeps the shipped default of Paddle, unconditionally) — there is no in-app UI toggle, matching the "not a V1 product feature" framing already used for this file's other env-var-gated developer switch.

**Dependency/packaging contract:** `[project.optional-dependencies].directml` in `pyproject.toml` pins `rapidocr==3.9.2` and `onnxruntime-directml==1.24.4` (the exact pair re-verified for this gate), both marked `sys_platform == 'win32'` so the extra is inert on Linux/macOS and cannot affect GitHub CI. It is a separate extra from `[ocr]`, not merged into it. **Update (M11 Stage ⑦-A packaging hardening, 2026-09-04):** the caution below that `[ocr]` and `[directml]` "must be installed into separate environments" was written from the upstream `onnxruntime`-name-collision risk in the abstract, but was never actually tested against this project's exact pinned pair until Stage ⑦-A's packaging preflight — `pip install -e ".[ocr,directml]"` together in one environment was verified to work cleanly (`rapidocr` does not pull in a conflicting bare `onnxruntime`), and all four backend combinations (Paddle×2, DirectML×2) were verified to construct and run real inference in the same process. GlyphCue's shipped PyInstaller package now bundles both extras together in one environment (see `PROJECT_STATUS.md`'s canonical build command) — this is empirically proven for the pinned versions above, not merely assumed; a version bump to either package should re-verify this before relying on it again. The ~21.2MB `PP-OCRv6_rec_small.onnx` recognition model (same PP-OCRv6 family as the Paddle P2 `TextRecognition` model, ONNX-exported) is not bundled or version-tracked by GlyphCue in source control — RapidOCR downloads and caches its own default model set on first use, the same pattern paddleocr/paddlepaddle already use; the packaged product does bundle these `.onnx` files directly (via `--collect-all rapidocr`, see below) so a fresh install never needs network access for them. `GLYPHCUE_DIRECTML_MODELS_DIR`/`GLYPHCUE_DIRECTML_PACKAGES_DIR` exist only as optional local overrides for offline/pinned-artifact test environments.

**What stays frozen:** this addendum does not touch `occupancy_normalized_distance`, the 0.300 grouping threshold, Beta-S, the 5fps scheduler, medoid calibration, caption identity evidence semantics, or the P2 recognition-only Paddle path in any way — `DirectMlOcrEngine` is a second, entirely separate implementation of the same frozen `OcrEngine`/`RegionOcrEngine` contract.

## Milestone 11 Stage ⑦ addendum: DirectML becomes the default-preferred backend, not opt-in (2026-09-04)

**Runtime policy corrected — superseding "opt-in only" above.** The
P3/P4B Confirmation Gates above proved DirectML real, safe (genuine
preflight + automatic Paddle fallback), and within the ≤5× realtime
performance target — but shipping it as a hidden opt-in meant a normal
Windows user launching `GlyphCue.exe` never actually got that
performance, silently defaulting instead to the CPU Paddle path's
19.7×–108.4× realtime cost (`enable_mkldnn=False`, a real workaround for
a `paddleocr==3.7.0`/`paddlepaddle==3.3.1` crash — see the base ADR
above; `PaddleOcrEngine` remains correct, just slow). A packaging
investigation (Stage ⑦-A/⑦-B/⑦-C, `PROJECT_STATUS.md`) surfaced this gap
concretely when a real packaged run measured ~20× realtime, prompting
Human Adjudication to close it as a small **Stage ⑦ Runtime Default
Corrective Gate**.

**What changed:** `src/glyphcue/ui/app.py`'s `_ocr_engine_factory`/
`_hybrid_detector_factory` now call `create_ocr_engine`/
`create_text_detector` with `prefer_directml=True` **by default** (no env
var needed). `GLYPHCUE_PREFER_DIRECTML_OCR`/`GLYPHCUE_PREFER_DIRECTML_DETECTOR`
were renamed to `GLYPHCUE_DISABLE_DIRECTML_OCR`/
`GLYPHCUE_DISABLE_DIRECTML_DETECTOR` and their polarity flipped: they are
now a DevQA/support override to force Paddle-only, not a switch a normal
user has to find and set to get accelerated performance.

**What did not change:** `create_ocr_engine`/`create_text_detector`
themselves (this ADR's `prefer_directml` parameter, its real
platform/package preflight, and its real DirectML initialization probe)
are byte-for-byte unchanged — only the caller's default flipped. Paddle
remains the automatic, correctness-preserving fallback on any
unsupported platform, missing install, or provider-init failure; there
is still exactly one product pipeline (`PRODUCTION_TRIGGER`) and
`DirectMlOcrEngine`/`DirectMlTextDetector` remain a second *backend*
inside it, not a second pipeline. The documented correctness trade-off
(RapidOCR's bundled recognition model showing non-zero CER on some
content where Paddle showed zero, per the Confirmation Gate above) is
unchanged and still applies — this policy change is about which backend
runs by default, not a claim that the trade-off no longer exists.

**Packaging:** the canonical PyInstaller build command
(`PROJECT_STATUS.md`) gained `--collect-all rapidocr` in the same gate —
without it, the packaged product had zero DirectML capacity at all (the
`rapidocr` package was entirely absent from the frozen bundle), which
would have made this default-preference change silently inert in the
shipped product even though it worked correctly from source.
