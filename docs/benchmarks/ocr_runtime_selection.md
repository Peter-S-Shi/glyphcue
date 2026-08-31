# OCR Runtime Benchmark — Milestone 3

**Candidates evaluated:** RapidOCR (ONNX Runtime backend) vs PaddleOCR (PaddlePaddle backend), the two initial candidates named in `ROADMAP.md` §10. No third runtime was added — neither candidate failed outright; the choice is a genuine tradeoff (see the ADR).

## Environment (for interpreting the numbers below)

- OS: Windows 10 (build 10.0.26200)
- Python: 3.11.9 (CPython, 64-bit) — V1 targets Python 3.12; the benchmark itself is Python-version-insensitive since it only exercises inference, not GlyphCue's own package
- CPU: 14 physical / 20 logical cores, 16.8 GB RAM (a developer workstation, not a constrained CI runner — absolute latency numbers should not be read as representative of end-user hardware; the RapidOCR vs PaddleOCR *comparison* is valid since both ran on the identical machine in the same session)
- CPU-only: no GPU was used or available to either engine (matches ROADMAP's mandatory CPU-only core path)
- Package versions: `rapidocr-onnxruntime==1.4.4`, `onnxruntime==1.29.0`, `opencv-python==5.0.0.93`, `paddleocr==3.7.0`, `paddlepaddle==3.3.1`, `paddlex==3.7.2`, `numpy==2.3.5`, `pillow==12.3.0`, `psutil==7.2.2`
- Benchmark script: `benchmarks/ocr_runtime_selection/run_benchmark.py` (not run in CI — installs 500MB+ of ML dependencies; run manually to reproduce)
- Raw results: `benchmarks/ocr_runtime_selection/benchmark_results.json`

## Corpus

Six generated, copyright-safe fixtures (`benchmarks/ocr_runtime_selection/corpus.py`), rendered from known ground-truth strings using Windows system fonts (Arial, SimHei, MS Gothic) — no scraped video frame or real subtitle screenshot is used anywhere:

| id | category | ground truth |
|---|---|---|
| `english_clean` | English | "The quick brown fox jumps over the lazy dog." |
| `chinese_clean` | Chinese | "今天天气非常好，我们一起去公园散步。" |
| `japanese_clean` | Japanese | "今日はとても良い天気ですね。" |
| `bilingual_crop` | Bilingual crop | "Hello, welcome!" / "你好，欢迎！" (two lines) |
| `low_quality_crop` | Low-quality crop | "Please stand by for further instructions." (Gaussian-blurred, contrast-reduced) |
| `subtitle_style_representative` | Representative subtitle style | "This is a burned-in subtitle example." (bold white text, black outline + drop shadow, gradient background) |

## Methodology

- Each engine is constructed once per language configuration it needs, with one throwaway warm-up call before timing begins. "Startup" below is engine construction (model load) time for the first/default language only.
- Per-item latency is the **median of 3 timed calls** after warm-up (`_median_latency` in `run_benchmark.py`).
- Memory is process RSS (via `psutil`), sampled at three points: baseline (before importing the vendor package), after model load, and peak (after all recognition calls). Deltas isolate the engine's own footprint from the Python interpreter's baseline.
- CER (Character Error Rate) = Levenshtein edit distance / length of the reference string (`benchmarks/ocr_runtime_selection/cer.py`), verified against the textbook "kitten"→"sitting" example (distance 3, CER 0.5) before use. No external ground-truth tool is involved — the reference strings are the literal constants in `corpus.py`, independently readable.

## Results

### Text quality (CER — lower is better; 0.0 = exact match)

| Item | RapidOCR | PaddleOCR |
|---|---|---|
| english_clean | 0.0 | 0.0 |
| chinese_clean | 0.0 | 0.0 |
| **japanese_clean** | **0.6429** | **0.0** |
| bilingual_crop | 0.0 | 0.0 |
| low_quality_crop | 0.0244 | 0.0 |
| subtitle_style_representative | 0.0 | 0.0 |

RapidOCR's Japanese failure is not a close call: it recognized `"今良天気。"` against a ground truth of `"今日はとても良い天気ですね。"` — it dropped most of the hiragana entirely. This traces to a real, explainable cause (see "Why," below), not noise.

### Performance and footprint

| Metric | RapidOCR | PaddleOCR |
|---|---|---|
| Startup (engine construction) | 1.00 s | 4.42 s |
| Per-item latency (median of 3, warm) | 3.0–3.2 s | 2.3–2.8 s |
| Memory after model load (delta from baseline) | +79.6 MB | +372.3 MB (one language) |
| Peak memory (after all 6 items, 3 languages loaded for PaddleOCR) | 130.0 MB | 884.4 MB |
| Installed package size (site-packages) | ~212 MB (rapidocr_onnxruntime 16 MB + onnxruntime 45 MB + opencv-python 151 MB) | ~413 MB (paddle 393 MB + paddleocr 1.4 MB + paddlex 19 MB) |
| Downloaded model weights | bundled in the pip package (no separate download) | ~177 MB, auto-downloaded on first use to `~/.paddlex/official_models` |
| **Total on-disk footprint** | **~212 MB** | **~590 MB** |

Absolute per-item latency numbers (3+ seconds for a ~300×50px crop) are high in both cases relative to what production selective-OCR would need — this reflects the unthrottled developer workstation and default (non-batched, non-tuned) inference settings, not a hard runtime limit. Milestone 4 (Selective OCR Evidence Pipeline) will need its own throughput-focused evaluation once real ROI-crop batching exists; this benchmark's job is only to pick the V1 default runtime.

### Multilingual support

- **RapidOCR**: one bundled recognition model (`ch_PP-OCRv4_rec_infer.onnx`) handles Chinese + English + (per its docs) some other scripts, but **no Japanese-specific model ships with `rapidocr_onnxruntime`**. Achieving RapidOCR-based Japanese accuracy would require separately sourcing and wiring a third-party Japanese ONNX model — a real, uncosted integration step, not evaluated here since it falls outside the package's default, documented usage.
- **PaddleOCR**: `lang=` selects a dedicated per-language pipeline (`en`, `ch`, `japan` were used here); each additional language is a separate model load (hence the higher peak memory once 3 languages are loaded). This is direct, first-class, documented multilingual support at the cost of more memory when many languages are active simultaneously.

### API / error behavior

- **RapidOCR**: `engine(image)` returns `(results, elapse)`; construction and inference both worked with defaults, no compatibility issues encountered.
- **PaddleOCR**: `PaddleOCR(lang=..., enable_mkldnn=True [default])` **crashed** on this environment's CPU with:
  ```
  NotImplementedError: (Unimplemented) ConvertPirAttribute2RuntimeAttribute not support
  [pir::ArrayAttribute<pir::DoubleAttribute>]
  ```
  This is a real version-compatibility bug between `paddleocr==3.7.0` and `paddlepaddle==3.3.1`'s default oneDNN-accelerated CPU execution path — not a corpus or usage error (it reproduced on the very first construction attempt, before any recognition call). The workaround, `enable_mkldnn=False`, fixed it completely and was used for every PaddleOCR measurement above. This is real packaging-friction evidence, not a hypothetical concern.
- **Default pipeline weight**: `PaddleOCR()` with no explicit flags loads a 5-model document pipeline (orientation classification, unwarping, textline orientation, detection, recognition) intended for scanned documents — a poor default for small subtitle ROI crops. All PaddleOCR measurements above used `use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False` to get a fair, subtitle-crop-appropriate comparison; this is worth carrying into the M3 adapter's defaults (already done in `PaddleOcrEngine`).

## Summary table

| Criterion | RapidOCR | PaddleOCR | Winner |
|---|---|---|---|
| Text quality (CJK, incl. Japanese) | Fails Japanese (CER 0.64) | Perfect on all 6 items | **PaddleOCR** |
| Startup time | 1.0 s | 4.4 s | RapidOCR |
| Steady-state latency | 3.0–3.2 s | 2.3–2.8 s | PaddleOCR |
| Memory footprint | ~80–130 MB | ~372–884 MB | RapidOCR |
| Package/model size | ~212 MB | ~590 MB | RapidOCR |
| Multilingual support | One model, missing Japanese | Explicit per-language, needs extra memory | PaddleOCR |
| API/error behavior | Clean, no issues | Real crash requiring a documented workaround | RapidOCR |

See `docs/adr/0001-ocr-runtime-selection.md` for the resulting V1 decision.
