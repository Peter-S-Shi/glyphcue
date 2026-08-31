"""Milestone 5 single-frame-baseline-vs-multi-frame-consensus evaluation,
on the real PaddleOcrEngine (V1 default runtime, see
docs/adr/0001-ocr-runtime-selection.md).

Run manually (not part of CI/pytest -- requires the optional `[ocr]`
extra): `python benchmarks/multi_frame_consensus/run_evaluation.py`

For each of 3 languages (English, Chinese, Japanese), generates 5
independently-degraded image variants of one ground-truth subtitle
line -- a mixed *synthetic* scenario, not a claim about how often this
degradation pattern occurs in real footage (no real-world frequency
evidence has been gathered for that). Runs the real OCR engine on each
variant, producing one Observation *per region* (mirroring exactly what
`build_ocr_evidence_job` does -- this script never joins region text
itself), then compares:

- single-frame baseline: the first variant's regions, joined by the
  real `aggregate_same_frame_observations` (the same same-frame join
  the production pipeline uses) -- what a pipeline with no cross-frame
  consensus step would show the user;
- multi-frame consensus: the real `reconstruct_cues_with_consensus`
  output over ALL 5 variants' region Observations -- same production
  entrypoint `reconstruct_cues_for_evidence_run` calls, so this
  evaluation exercises the identical aggregation + consensus path a
  real evidence run would.

CER (Character Error Rate) is the real formula from
`benchmarks/ocr_runtime_selection/cer.py`: Levenshtein distance /
len(reference) -- NOT `text_similarity.character_similarity` (a
different, symmetric, max-length-normalized formula used for
consensus's own internal grouping/voting, not for scoring against
ground truth). Writes results to evaluation_results.json next to this
script.
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fixture import ITEMS, generate_all_noisy_variants, generate_mixed_variants  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "ocr_runtime_selection"))

from cer import character_error_rate  # noqa: E402

from glyphcue.adapters.paddleocr_engine import PaddleOcrEngine  # noqa: E402
from glyphcue.application.consensus_reconstruction import (  # noqa: E402
    reconstruct_cues_with_consensus,
)
from glyphcue.application.frame_reading_aggregation import (  # noqa: E402
    aggregate_same_frame_observations,
)
from glyphcue.domain.observation import Observation  # noqa: E402
from glyphcue.domain.provenance import Provenance, ProvenanceKind  # noqa: E402

RESULTS_PATH = Path(__file__).parent / "evaluation_results.json"
_SEED = 20260831  # fixed seed: reproducible noise across runs


def _region_observations(item, variant_index: int, regions) -> list[Observation]:
    frame_reference = f"{item.id}-variant-{variant_index}"
    return [
        Observation(
            id=f"{item.id}-{variant_index}-region{region_index}",
            text=region.text,
            start_time=float(variant_index),
            end_time=float(variant_index) + 0.001,
            provenance=Provenance(kind=ProvenanceKind.OCR_ENGINE, source="PaddleOCR"),
            language=item.language,
            confidence=region.confidence,
            geometry=region.geometry,
            frame_reference=frame_reference,
        )
        for region_index, region in enumerate(regions)
    ]


def _evaluate_item(item, engine, variant_generator) -> dict:
    variants = variant_generator(item, seed=_SEED)

    all_region_observations: list[Observation] = []
    reading_texts = []
    for variant_index, variant_image in enumerate(variants):
        regions = engine.recognize(variant_image)
        region_observations = _region_observations(item, variant_index, regions)
        all_region_observations.extend(region_observations)
        reading_texts.append("".join(region.text for region in regions))

    # Single-frame baseline: only variant 0's regions, joined by the
    # SAME production same-frame aggregation the real pipeline uses --
    # this script does not join region text itself.
    first_frame_observations = [
        observation for observation in all_region_observations if observation.start_time == 0.0
    ]
    single_frame_aggregated = aggregate_same_frame_observations(first_frame_observations)
    single_frame_text = single_frame_aggregated[0].text if single_frame_aggregated else ""
    single_frame_cer = round(character_error_rate(item.ground_truth, single_frame_text), 4)

    # Multi-frame consensus: the real production entrypoint, given every
    # region Observation across all 5 variants.
    cues, _diagnostics = reconstruct_cues_with_consensus(all_region_observations)
    # If OCR noise was severe enough that the grouping step didn't treat
    # all 5 readings as one state, consensus text is the longest-running
    # Cue's text (the algorithm's own idea of "the state"); this is
    # recorded honestly as a real failure mode, not hidden.
    consensus_cue = max(cues, key=lambda cue: len(cue.language_layers[0].observation_ids))
    consensus_text = consensus_cue.language_layers[0].text
    consensus_cer = round(character_error_rate(item.ground_truth, consensus_text), 4)

    return {
        "id": item.id,
        "language": item.language,
        "ground_truth": item.ground_truth,
        "readings": reading_texts,
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
            "mixed_synthetic_1_degraded_4_clean", generate_mixed_variants, engines
        )
        all_noisy = _run_scenario(
            "all_5_heavily_degraded", generate_all_noisy_variants, engines
        )
    finally:
        for engine in engines.values():
            engine.shutdown()

    summary = {"mixed_synthetic_1_degraded_4_clean": mixed, "all_5_heavily_degraded": all_noisy}
    RESULTS_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {RESULTS_PATH}")
    print(f"mixed scenario: single_frame={mixed['mean_single_frame_cer']} consensus={mixed['mean_consensus_cer']}")
    print(f"all-noisy scenario: single_frame={all_noisy['mean_single_frame_cer']} consensus={all_noisy['mean_consensus_cer']}")


if __name__ == "__main__":
    main()
