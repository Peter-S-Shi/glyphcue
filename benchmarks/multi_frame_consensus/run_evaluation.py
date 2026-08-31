"""Milestone 5 single-frame-baseline-vs-multi-frame-consensus evaluation,
on the real PaddleOcrEngine (V1 default runtime, see
docs/adr/0001-ocr-runtime-selection.md).

Run manually (not part of CI/pytest -- requires the optional `[ocr]`
extra): `python benchmarks/multi_frame_consensus/run_evaluation.py`

For each of 3 languages (English, Chinese, Japanese), generates 5
independently-degraded image variants of one ground-truth subtitle
line, runs the real OCR engine on each (5 real, possibly-noisy
readings), then compares:

- single-frame baseline: CER of the FIRST reading against ground truth
  (what a pipeline with no consensus step would show the user);
- multi-frame consensus: CER of `reconstruct_cues_with_consensus`'s
  output, fed all 5 readings as Observations, against ground truth.

Both numbers come from the real, production `reconstruct_cues_with_consensus`
function and a real OCR engine -- nothing here is estimated. Writes
results to evaluation_results.json next to this script.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fixture import ITEMS, generate_all_noisy_variants, generate_mixed_variants  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from glyphcue.adapters.paddleocr_engine import PaddleOcrEngine  # noqa: E402
from glyphcue.application.consensus_reconstruction import (  # noqa: E402
    reconstruct_cues_with_consensus,
)
from glyphcue.application.text_similarity import character_similarity  # noqa: E402
from glyphcue.domain.observation import Observation  # noqa: E402
from glyphcue.domain.provenance import Provenance, ProvenanceKind  # noqa: E402

RESULTS_PATH = Path(__file__).parent / "evaluation_results.json"
_SEED = 20260831  # fixed seed: reproducible noise across runs


def _cer(reference: str, hypothesis: str) -> float:
    return round(1 - character_similarity(reference, hypothesis), 4)


def _evaluate_item(item, engine, variant_generator) -> dict:
    variants = variant_generator(item, seed=_SEED)

    readings = []
    for variant_image in variants:
        regions = engine.recognize(variant_image)
        text = "".join(region.text for region in regions)
        confidence = regions[0].confidence if regions else None
        readings.append((text, confidence))

    observations = [
        Observation(
            id=f"{item.id}-{index}",
            text=text,
            start_time=float(index),
            end_time=float(index) + 0.001,
            provenance=Provenance(kind=ProvenanceKind.OCR_ENGINE, source="PaddleOCR"),
            language=item.language,
            confidence=confidence,
        )
        for index, (text, confidence) in enumerate(readings)
    ]

    single_frame_text = readings[0][0]
    single_frame_cer = _cer(item.ground_truth, single_frame_text)

    cues, diagnostics = reconstruct_cues_with_consensus(observations)
    # If OCR noise was severe enough that the grouping step didn't treat
    # all 5 readings as one state, consensus text is the longest-running
    # Cue's text (the algorithm's own idea of "the state"); this is
    # recorded honestly as a real failure mode, not hidden.
    consensus_cue = max(cues, key=lambda cue: len(cue.language_layers[0].observation_ids))
    consensus_text = consensus_cue.language_layers[0].text
    consensus_cer = _cer(item.ground_truth, consensus_text)

    return {
        "id": item.id,
        "language": item.language,
        "ground_truth": item.ground_truth,
        "readings": [text for text, _confidence in readings],
        "single_frame": {"text": single_frame_text, "cer": single_frame_cer},
        "consensus": {
            "text": consensus_text,
            "cer": consensus_cer,
            "cue_count": len(cues),
            "observations_in_winning_cue": len(consensus_cue.language_layers[0].observation_ids),
        },
        "cer_improvement": round(single_frame_cer - consensus_cer, 4),
    }


def _run_scenario(name: str, variant_generator, engines: dict) -> dict:
    results = [_evaluate_item(item, engines[item.language], variant_generator) for item in ITEMS]
    return {
        "scenario": name,
        "results": results,
        "mean_single_frame_cer": round(
            sum(r["single_frame"]["cer"] for r in results) / len(results), 4
        ),
        "mean_consensus_cer": round(sum(r["consensus"]["cer"] for r in results) / len(results), 4),
    }


def main() -> None:
    engines = {}
    try:
        for item in ITEMS:
            if item.language not in engines:
                engine = PaddleOcrEngine(language=item.language)
                engine.initialize()
                engines[item.language] = engine

        mixed = _run_scenario(
            "mixed_4_clean_1_degraded", generate_mixed_variants, engines
        )
        all_noisy = _run_scenario(
            "all_5_heavily_degraded", generate_all_noisy_variants, engines
        )
    finally:
        for engine in engines.values():
            engine.shutdown()

    summary = {"mixed_4_clean_1_degraded": mixed, "all_5_heavily_degraded": all_noisy}
    RESULTS_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {RESULTS_PATH}")
    print(f"mixed scenario: single_frame={mixed['mean_single_frame_cer']} consensus={mixed['mean_consensus_cer']}")
    print(f"all-noisy scenario: single_frame={all_noisy['mean_single_frame_cer']} consensus={all_noisy['mean_consensus_cer']}")


if __name__ == "__main__":
    main()
