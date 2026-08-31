# OCR Runtime Benchmark — Milestone 3

**Candidates evaluated:** RapidOCR (ONNX Runtime backend) vs PaddleOCR (PaddlePaddle backend), the two initial candidates named in `ROADMAP.md` §10. No third runtime was added — neither candidate failed outright; the choice is a genuine tradeoff (see the ADR).

## Environment (for interpreting the numbers below)

- OS: Windows 11 Home (build 10.0.26200)
- Python: **3.12.10 (CPython, 64-bit)** — matches V1's actual target (`requires-python = ">=3.12"` in `pyproject.toml`). An earlier pass of this benchmark ran on Python 3.11.9 and described its results as "Python-version-insensitive since it only exercises inference, not GlyphCue's own package" — that claim was never verified and has been retracted; the numbers below are a real Python 3.12 re-run on the same machine, not an assumption carried over from 3.11. Re-running on 3.12 happened to resolve the identical `paddleocr==3.7.0` / `paddlepaddle==3.3.1` pair from unpinned `>=` constraints, which is itself now moot: `pyproject.toml`'s `[ocr]` extra pins these exactly, so future installs cannot silently drift onto an unverified pair without a maintainer explicitly bumping the pin and re-running this benchmark.
- CPU: 14 physical / 20 logical cores, 15.7 GB RAM (a developer workstation, not a constrained CI runner or an isolated benchmark rig — absolute latency numbers should not be read as representative of end-user hardware, and vary noticeably run-to-run on this machine depending on background load: repeated runs of the identical script/code measured per-item latency anywhere from ~0.8 s to ~3.3 s across sessions. The RapidOCR vs PaddleOCR *comparison* is still valid since both engines ran back-to-back on the same machine in the same process for every run, so both are affected by the same contention at the same time)
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

- Each engine is constructed once per language configuration it needs. **Every** language configuration (not just the first/default one) gets its own throwaway warm-up call immediately after construction, discarded before timing begins. An earlier pass of this benchmark warmed up only PaddleOCR's default (`en`) engine and then timed the Chinese and Japanese engines' *first-ever* call as part of their "steady-state" median — silently folding one-time JIT/session-setup cost into the reported per-item latency for those two languages. That bug is fixed: `run_benchmark.py`'s `get_engine()` now runs a warm-up call for every new language the moment it's constructed.
- **`startup_seconds`** is import + default-language engine construction **only, for both engines** — warm-up is deliberately excluded from it. An earlier pass computed RapidOCR's startup as import+construction but PaddleOCR's as import+construction+warm-up (because its warm-up call happened before the startup timer was read), an apples-to-oranges comparison. That asymmetry is fixed: both engines now stop their startup timer immediately after default-language construction, before any warm-up call runs. PaddleOCR's per-language construction cost for `ch`/`japan` is reported separately in `startup_seconds_by_language` (raw JSON), also construction-only.
- Per-item latency is the **median of 3 timed calls** after warm-up (`_median_latency` in `run_benchmark.py`).
- Memory is process RSS (via `psutil`, each sample forcing `gc.collect()` first). **`max_observed_rss_mb`** is the maximum across explicit, discrete samples taken after every model load, after every warm-up call, and after every per-item call (`_MaxObservedRss` in `run_benchmark.py`) — it is **not** a true/continuous peak and is reported under that name deliberately, not as "peak memory": it can miss a transient spike that rises and falls entirely between two sample points, and the forced `gc.collect()` before each sample can itself pull the reading down relative to what an un-collected true peak would show. An earlier pass took exactly one RSS reading after the whole run finished and called that "peak memory," which understates the risk of missing the actual high point even more than the current per-step sampling does; the current approach is a real improvement but is still honestly labeled as an approximation, not exact.
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
| Startup (import + default-language construction only, warm-up excluded — see Methodology) | 1.55 s | 4.57 s; separate construction-only costs: `en` 2.58 s, `ch` 1.33 s, `japan` 1.35 s — these are not additive components of the 4.57 s figure (that figure already includes the import cost and `en`'s own construction, measured independently on first use of each language — see `startup_seconds_by_language` in the raw JSON) |
| Per-item latency (median of 3, warm — genuinely per-language-warm, see Methodology) | 2.95–3.12 s | 2.34–2.94 s |
| Memory after model load (delta from baseline) | +70.0 MB | +367.9 MB (one language) |
| `max_observed_rss_mb` (see Methodology — an approximation, not a true peak) | 116.1 MB | 789.3 MB |
| Installed package size (site-packages) | ~212 MB (rapidocr_onnxruntime 16 MB + onnxruntime 45 MB + opencv-python 151 MB) | ~413 MB (paddle 393 MB + paddleocr 1.4 MB + paddlex 19 MB) |
| Downloaded model weights | bundled in the pip package (no separate download) | ~177 MB, auto-downloaded on first use to `~/.paddlex/official_models` |
| **Total on-disk footprint** | **~212 MB** | **~590 MB** |

The per-item latency numbers above are from the most recent full re-run (fixing the startup-timing asymmetry described in Methodology). They read higher than an intermediate re-run of this same fixed code measured minutes earlier on the same idle machine (RapidOCR 1.15–1.38 s, PaddleOCR 0.80–1.04 s) — repeated runs on this developer workstation have shown per-item latency ranging from under 1 s to over 3 s for identical code and corpus, apparently from background load this machine cannot fully isolate (CPU-percent sampled immediately before a run showed under 6% utilization, yet the run itself still ran slow, so the contention is bursty and not something a pre-run idle check reliably predicts). What has stayed stable across every re-run: PaddleOCR's CER is 0.0 on all 6 items, RapidOCR fails Japanese every time (CER 0.6429), and PaddleOCR's per-item latency is consistently lower than or comparable to RapidOCR's in the same run — the runtime decision does not depend on the absolute latency numbers, only on their relative ordering plus the CER results, both of which are reproducible. Absolute per-item latency in the seconds range for a small crop reflects the unthrottled developer workstation and default (non-batched, non-tuned) inference settings, not a hard runtime limit. Milestone 4 (Selective OCR Evidence Pipeline) will need its own throughput-focused evaluation once real ROI-crop batching exists; this benchmark's job is only to pick the V1 default runtime.

### Multilingual support

- **RapidOCR**: one bundled recognition model (`ch_PP-OCRv4_rec_infer.onnx`) handles Chinese + English + (per its docs) some other scripts, but **no Japanese-specific model ships with `rapidocr_onnxruntime`**. Achieving RapidOCR-based Japanese accuracy would require separately sourcing and wiring a third-party Japanese ONNX model — a real, uncosted integration step, not evaluated here since it falls outside the package's default, documented usage.
- **PaddleOCR**: `lang=` selects a dedicated per-language pipeline (`en`, `ch`, `japan` were used here); each additional language is a separate model load (hence the higher `max_observed_rss_mb` once 3 languages are loaded). This is direct, first-class, documented multilingual support at the cost of more memory when many languages are active simultaneously.

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
| Startup time (import + default-language construction; warm-up excluded) | 1.55 s | 4.57 s | RapidOCR |
| Steady-state latency | 2.95–3.12 s (varies run-to-run, see above) | 2.34–2.94 s (varies run-to-run, see above) | PaddleOCR |
| Memory footprint | ~70–116 MB | ~368–789 MB | RapidOCR |
| Package/model size | ~212 MB | ~590 MB | RapidOCR |
| Multilingual support | One model, missing Japanese | Explicit per-language, needs extra memory | PaddleOCR |
| API/error behavior | Clean, no issues | Real crash requiring a documented workaround | RapidOCR |

See `docs/adr/0001-ocr-runtime-selection.md` for the resulting V1 decision.
