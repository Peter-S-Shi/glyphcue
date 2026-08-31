"""Milestone 3 OCR runtime benchmark: RapidOCR (ONNX Runtime) vs PaddleOCR.

Run manually (not part of CI/pytest -- installs ~500MB+ of ML
dependencies): `python benchmarks/ocr_runtime_selection/run_benchmark.py`

Methodology:
- Each engine is constructed once per language configuration needed.
  EVERY language configuration gets its own throwaway warm-up call
  (discarded) immediately after construction, before its timed calls
  begin -- not just the first/default language -- so per-item latency
  never silently includes a language's first-call JIT/session-setup
  cost.
- "startup_seconds" is import + default-language engine construction
  ONLY, for both engines -- warm-up is deliberately excluded so the two
  engines are timed on the same basis. PaddleOCR's per-language
  construction cost for additional languages is reported separately in
  "startup_seconds_by_language" (also construction-only, warm-up
  excluded there too).
- Per-item latency is the median of 3 timed calls after warm-up.
- Process RSS is sampled via psutil (each sample runs gc.collect()
  first) at baseline (before importing the vendor package), after each
  language's model load, after each language's warm-up call, and after
  every per-item call. "max_observed_rss_mb" is the maximum of these
  explicit, discrete post-step samples -- NOT a true/continuous peak.
  It can miss a transient spike that occurs and is released again
  *during* a call, between two samples, and the forced gc.collect()
  before every sample can itself pull memory down below what a
  non-GC'd reading would show. Treat it as a conservative, reproducible
  lower-bound-ish indicator of memory pressure, not an exact peak.
- CER uses a plain Levenshtein edit distance (see
  glyphcue.evaluation.metrics.character_error_rate) against the
  known ground truth strings in corpus.py -- no external ASR/OCR
  ground-truth tool is used, so results are independently checkable by
  reading corpus.py.

Writes results to benchmark_results.json next to this script.
"""

from __future__ import annotations

import gc
import json
import statistics
import sys
import time
from pathlib import Path

import numpy as np
import psutil
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from corpus import CORPUS, generate_corpus  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
from glyphcue.evaluation.metrics import character_error_rate  # noqa: E402

CORPUS_DIR = Path(__file__).parent / "generated_corpus"
RESULTS_PATH = Path(__file__).parent / "benchmark_results.json"
PROCESS = psutil.Process()


def _rss_mb() -> float:
    gc.collect()
    return PROCESS.memory_info().rss / (1024 * 1024)


class _MaxObservedRss:
    """Tracks the maximum RSS across repeated, explicit `sample()` calls.

    This is NOT a true/continuous peak tracker: it only knows the RSS at
    the discrete moments `sample()` is called (each of which forces a
    gc.collect() first -- see _rss_mb). A single end-of-run RSS snapshot
    would be worse (it could miss the heaviest point in the run
    entirely), so `sample()` is called after every load/warm-up/
    inference step to approximate the peak -- but a transient spike that
    rises and falls entirely between two sample points is still
    invisible to this, and gc.collect() before each sample can itself
    lower the reading relative to an un-collected true peak. Report this
    value as "max_observed_rss_mb", never as "peak" or "true peak".
    """

    def __init__(self, initial_mb: float) -> None:
        self.max_observed_mb = initial_mb

    def sample(self) -> float:
        current_mb = _rss_mb()
        self.max_observed_mb = max(self.max_observed_mb, current_mb)
        return current_mb


def _median_latency(fn, repeats: int = 3) -> float:
    times = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        times.append(time.perf_counter() - start)
    return statistics.median(times)


def _score(item, texts: list[str]) -> dict:
    hypothesis = "".join(texts)
    # ground truth for bilingual_crop stores two lines separated by "|";
    # compare against them joined so multi-line recognition still scores
    # correctly regardless of how many text regions the engine reports.
    reference = "".join(item.ground_truth.split("|"))
    cer = character_error_rate(reference, hypothesis)
    return {"recognized_text": hypothesis, "cer": round(cer, 4)}


def benchmark_rapidocr() -> dict:
    baseline_mb = _rss_mb()
    peak = _MaxObservedRss(baseline_mb)
    t0 = time.perf_counter()
    from rapidocr_onnxruntime import RapidOCR

    engine = RapidOCR()
    startup_seconds = time.perf_counter() - t0
    after_load_mb = peak.sample()

    warmup_image = np.array(Image.open(CORPUS_DIR / f"{CORPUS[0].id}.png"))
    engine(warmup_image)  # warm-up call, discarded
    peak.sample()

    per_item = {}
    for item in CORPUS:
        image = np.array(Image.open(CORPUS_DIR / f"{item.id}.png"))

        def _call():
            return engine(image)

        latency = _median_latency(_call)
        peak.sample()
        result, _elapse = engine(image)
        peak.sample()
        texts = [r[1] for r in result] if result else []
        entry = {"latency_seconds": round(latency, 4)}
        entry.update(_score(item, texts))
        per_item[item.id] = entry

    return {
        "engine_name": "RapidOCR (onnxruntime backend)",
        "startup_seconds": round(startup_seconds, 4),
        "memory_baseline_mb": round(baseline_mb, 1),
        "memory_after_load_mb": round(after_load_mb, 1),
        "memory_after_load_delta_mb": round(after_load_mb - baseline_mb, 1),
        "max_observed_rss_mb": round(peak.max_observed_mb, 1),
        "per_item": per_item,
    }


def benchmark_paddleocr() -> dict:
    baseline_mb = _rss_mb()
    peak = _MaxObservedRss(baseline_mb)
    t0 = time.perf_counter()
    from paddleocr import PaddleOCR

    warmup_image = np.array(Image.open(CORPUS_DIR / f"{CORPUS[0].id}.png").convert("RGB"))
    engines_by_lang: dict[str, "PaddleOCR"] = {}
    startup_seconds_by_lang: dict[str, float] = {}
    warmed_up_langs: set[str] = set()

    def _construct(lang: str) -> None:
        lang_t0 = time.perf_counter()
        # enable_mkldnn=False works around a real crash observed with
        # this paddleocr==3.7.0 / paddlepaddle==3.3.1 pairing:
        # NotImplementedError: (Unimplemented)
        # ConvertPirAttribute2RuntimeAttribute not support
        # [pir::ArrayAttribute<pir::DoubleAttribute>] -- the default
        # oneDNN-accelerated CPU path is broken in this environment.
        # See the ADR for this as packaging-friction evidence.
        engines_by_lang[lang] = PaddleOCR(
            lang=lang,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            enable_mkldnn=False,
        )
        # Construction-only elapsed -- warm-up (below, in get_engine) is
        # timed and reported separately so it never inflates this.
        startup_seconds_by_lang[lang] = time.perf_counter() - lang_t0
        peak.sample()

    def get_engine(lang: str):
        """Construct (first use only) and warm up (first use only) the
        engine for `lang`, returning it ready for timed calls."""
        if lang not in engines_by_lang:
            _construct(lang)
        if lang not in warmed_up_langs:
            engines_by_lang[lang].predict(warmup_image)  # warm-up call, discarded
            peak.sample()
            warmed_up_langs.add(lang)
        return engines_by_lang[lang]

    _construct("en")
    # startup_seconds = import + default-language construction ONLY,
    # matching RapidOCR's definition above -- warm-up is excluded here
    # (get_engine's warm-up for "en" happens later, on first use in the
    # per-item loop below) so the two engines are timed on the same
    # basis.
    startup_seconds = time.perf_counter() - t0
    after_load_mb = peak.sample()

    lang_by_item = {
        "english_clean": "en",
        "chinese_clean": "ch",
        "japanese_clean": "japan",
        "bilingual_crop": "ch",  # PaddleOCR has no single en+zh model; ch model also covers Latin digits/letters reasonably
        "low_quality_crop": "en",
        "subtitle_style_representative": "en",
    }

    per_item = {}
    for item in CORPUS:
        lang = lang_by_item[item.id]
        engine = get_engine(lang)  # constructs + warms up on first use of a language
        image = np.array(Image.open(CORPUS_DIR / f"{item.id}.png").convert("RGB"))

        def _call():
            return engine.predict(image)

        latency = _median_latency(_call)
        peak.sample()
        result = engine.predict(image)
        peak.sample()
        texts = list(result[0]["rec_texts"]) if result and result[0].get("rec_texts") else []
        entry = {"latency_seconds": round(latency, 4)}
        entry.update(_score(item, texts))
        per_item[item.id] = entry

    return {
        "engine_name": "PaddleOCR (PaddlePaddle backend)",
        "startup_seconds": round(startup_seconds, 4),
        "startup_seconds_by_language": {
            lang: round(secs, 4) for lang, secs in startup_seconds_by_lang.items()
        },
        "memory_baseline_mb": round(baseline_mb, 1),
        "memory_after_load_mb": round(after_load_mb, 1),
        "memory_after_load_delta_mb": round(after_load_mb - baseline_mb, 1),
        "max_observed_rss_mb": round(peak.max_observed_mb, 1),
        "languages_requiring_separate_model_load": sorted(engines_by_lang.keys()),
        "per_item": per_item,
    }


def main() -> None:
    generate_corpus(CORPUS_DIR)

    results = {}
    print("Benchmarking RapidOCR...")
    results["rapidocr"] = benchmark_rapidocr()
    print("Benchmarking PaddleOCR...")
    results["paddleocr"] = benchmark_paddleocr()

    RESULTS_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {RESULTS_PATH}")


if __name__ == "__main__":
    main()
