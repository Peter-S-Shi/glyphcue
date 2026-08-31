# OCR Runtime Benchmark — Milestone 3

**Candidates evaluated:** RapidOCR (ONNX Runtime backend) vs PaddleOCR (PaddlePaddle backend), the two initial candidates named in `ROADMAP.md` §10. No third runtime was added — neither candidate failed outright; the choice is a genuine tradeoff (see the ADR).

## Environment (for interpreting the numbers below)

- OS: Windows 11 Home (build 10.0.26200)
- Python: **3.12.10 (CPython, 64-bit)** — matches V1's actual target (`requires-python = ">=3.12"` in `pyproject.toml`). An earlier pass of this benchmark ran on Python 3.11.9 and described its results as "Python-version-insensitive since it only exercises inference, not GlyphCue's own package" — that claim was never verified and has been retracted; the numbers below are a real Python 3.12 re-run on the same machine, not an assumption carried over from 3.11. Re-running on 3.12 happened to resolve the identical `paddleocr==3.7.0` / `paddlepaddle==3.3.1` pair from unpinned `>=` constraints, which is itself now moot: `pyproject.toml`'s `[ocr]` extra pins these exactly, so future installs cannot silently drift onto an unverified pair without a maintainer explicitly bumping the pin and re-running this benchmark.
- CPU: 14 physical / 20 logical cores, 15.7 GB RAM (a developer workstation, not a constrained CI runner — absolute latency numbers should not be read as representative of end-user hardware; the RapidOCR vs PaddleOCR *comparison* is valid since both ran on the identical machine in the same session)
- CPU-only: no GPU was used or available to either engine (matches ROADMAP's mandatory CPU-only core path)
- Package versions: `rapidocr-onnxruntime==1.4.4`, `onnxruntime==1.29.0`, `opencv-python==5.0.0.93`, `paddleocr==3.7.0`, `paddlepaddle==3.3.1`, `paddlex==3.7.2`, `numpy==2.3.5`, `pillow==12.3.0`, `psutil==7.2.2` — identical to the earlier 3.11 run's versions; only the Python interpreter and the measurement methodology (see below) changed.
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

- Each engine is constructed once per language configuration it needs. **Every** language configuration (not just the first/default one) gets its own throwaway warm-up call immediately after construction, discarded before timing begins. An earlier pass of this benchmark warmed up only PaddleOCR's default (`en`) engine and then timed the Chinese and Japanese engines' *first-ever* call as part of their "steady-state" median — silently folding one-time JIT/session-setup cost into the reported per-item latency for those two languages. That bug is fixed: `run_benchmark.py`'s `get_engine()` now runs a warm-up call for every new language the moment it's constructed. "Startup" below remains engine construction (model load) time for the first/default language only.
- Per-item latency is the **median of 3 timed calls** after warm-up (`_median_latency` in `run_benchmark.py`).
- Memory is process RSS (via `psutil`). "Peak" is a **running maximum** sampled after every model load and after every per-item call (`_PeakRss` in `run_benchmark.py`), not a single snapshot taken after the run finished. The earlier pass took one RSS reading at the very end and reported it as "peak memory" — that is not what peak means (the true high point could occur mid-run and be partly reclaimed by GC before a final reading), so it has been corrected to an actual running maximum. Baseline is taken before importing the vendor package; deltas isolate the engine's own footprint from the Python interpreter's baseline.
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
| Startup (default-language engine construction) | 1.60 s | 4.03 s (1.67 s `en` + 0.69 s `ch` + 0.71 s `japan`, each measured on first use — see `startup_seconds_by_language` in the raw JSON) |
| Per-item latency (median of 3, warm — now genuinely per-language-warm, see Methodology) | 1.15–1.38 s | 0.80–1.04 s |
| Memory after model load (delta from baseline) | +68.9 MB | +389.3 MB (one language) |
| Peak memory (running max across the whole run — see Methodology) | 114.3 MB | 791.8 MB |
| Installed package size (site-packages) | ~212 MB (rapidocr_onnxruntime 16 MB + onnxruntime 45 MB + opencv-python 151 MB) | ~413 MB (paddle 393 MB + paddleocr 1.4 MB + paddlex 19 MB) |
| Downloaded model weights | bundled in the pip package (no separate download) | ~177 MB, auto-downloaded on first use to `~/.paddlex/official_models` |
| **Total on-disk footprint** | **~212 MB** | **~590 MB** |

The per-item latency numbers above supersede an earlier pass that reported 3.0–3.2 s (RapidOCR) and 2.3–2.8 s (PaddleOCR): that pass warmed up only PaddleOCR's default language before timing, so the Chinese/Japanese rows' "warm" latency silently included a real first-call cost (see Methodology). The corrected numbers are lower for both engines and PaddleOCR's advantage over RapidOCR is now larger, not smaller — the corrective did not change the runtime decision. Absolute per-item latency (under 1.5 seconds for a ~300×50px crop, even after the fix) is still high relative to what production selective-OCR throughput would need — this reflects the unthrottled developer workstation and default (non-batched, non-tuned) inference settings, not a hard runtime limit. Milestone 4 (Selective OCR Evidence Pipeline) will need its own throughput-focused evaluation once real ROI-crop batching exists; this benchmark's job is only to pick the V1 default runtime.

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
| Startup time | 1.6 s | 4.0 s | RapidOCR |
| Steady-state latency | 1.15–1.38 s | 0.80–1.04 s | PaddleOCR |
| Memory footprint | ~69–114 MB | ~389–792 MB | RapidOCR |
| Package/model size | ~212 MB | ~590 MB | RapidOCR |
| Multilingual support | One model, missing Japanese | Explicit per-language, needs extra memory | PaddleOCR |
| API/error behavior | Clean, no issues | Real crash requiring a documented workaround | RapidOCR |

See `docs/adr/0001-ocr-runtime-selection.md` for the resulting V1 decision.
