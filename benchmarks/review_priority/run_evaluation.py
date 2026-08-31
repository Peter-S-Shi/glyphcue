"""Milestone 7 Review Priority evaluation: does ranking Cues by
`compute_review_priority`'s score actually surface more real
reconstruction errors than reviewing the same number of Cues in random
order?

This is a synthetic, constructed evaluation, not a claim about real
subtitle error rates -- no scraped video, subtitle, or transcript data
is used anywhere. A ground-truth "this Cue's reconstructed text is
actually wrong" label is assigned per synthetic Cue independently of
its evidence quality, then evidence quality (OCR confidence,
disagreement, missing/ambiguous language layers) is generated with a
deliberate but IMPERFECT correlation to that label -- errors are more
likely, not certain, to come with degraded evidence, mirroring the real
claim being tested ("worse evidence tends to mean worse reconstructions,
not always"). The real, unmodified production `compute_review_priority`
+ `review_signals_from_consensus_diagnostics` functions rank the
synthetic Cues; nothing about the ranking logic is specific to this
benchmark.

If ranking does not outperform random review here, that is reported
honestly in the output -- this script does not tune itself until the
numbers look good.

Run manually:
    python -m benchmarks.review_priority.run_evaluation
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path

from glyphcue.application.consensus_reconstruction import ConsensusDiagnostics
from glyphcue.application.review_priority import (
    compute_review_priority,
    review_signals_from_consensus_diagnostics,
)
from glyphcue.domain.observation import Observation
from glyphcue.domain.provenance import Provenance, ProvenanceKind

_RESULTS_PATH = Path(__file__).parent / "evaluation_results.json"
_CUE_COUNT = 200
_SEED = 20260831
_TOP_FRACTIONS = (0.1, 0.2, 0.3)


@dataclass(frozen=True)
class SyntheticCue:
    cue_id: str
    is_actually_wrong: bool
    diagnostics: ConsensusDiagnostics
    observations: list[Observation]


def _make_observation(cue_id: str, index: int, confidence: float) -> Observation:
    return Observation(
        id=f"{cue_id}-obs-{index}",
        text="synthetic reading",
        start_time=0.0,
        end_time=1.0,
        provenance=Provenance(kind=ProvenanceKind.OCR_ENGINE, source="synthetic"),
        confidence=confidence,
    )


def generate_synthetic_cues(count: int, seed: int) -> list[SyntheticCue]:
    rng = random.Random(seed)
    cues: list[SyntheticCue] = []
    for index in range(count):
        cue_id = f"cue-{index}"
        # Ground truth: ~25% of Cues have a genuinely wrong reconstruction,
        # assigned independently of the evidence quality generated below.
        is_wrong = rng.random() < 0.25

        # Evidence quality is CORRELATED but not deterministic: a wrong
        # Cue is more likely (not certain) to have degraded evidence, and
        # a correct Cue is more likely (not certain) to have clean
        # evidence -- a real, imperfect signal, not a tautology.
        if is_wrong:
            confidence = rng.uniform(0.3, 0.95)
            had_disagreement = rng.random() < 0.6
        else:
            confidence = rng.uniform(0.6, 1.0)
            had_disagreement = rng.random() < 0.1

        observations = [
            _make_observation(cue_id, 0, confidence),
            _make_observation(cue_id, 1, confidence + rng.uniform(-0.05, 0.05)),
        ]
        diagnostics = ConsensusDiagnostics(
            cue_id=cue_id,
            observation_count=len(observations),
            distinct_text_count=2 if had_disagreement else 1,
            agreement_ratio=0.5 if had_disagreement else 1.0,
            had_disagreement=had_disagreement,
        )
        cues.append(
            SyntheticCue(
                cue_id=cue_id,
                is_actually_wrong=is_wrong,
                diagnostics=diagnostics,
                observations=observations,
            )
        )
    return cues


def _recall_at_fraction(ranked_ids: list[str], wrong_ids: set[str], fraction: float) -> float:
    if not wrong_ids:
        return 0.0
    top_n = max(1, round(len(ranked_ids) * fraction))
    reviewed = set(ranked_ids[:top_n])
    captured = len(reviewed & wrong_ids)
    return captured / len(wrong_ids)


def run() -> dict:
    synthetic_cues = generate_synthetic_cues(_CUE_COUNT, _SEED)
    wrong_ids = {cue.cue_id for cue in synthetic_cues if cue.is_actually_wrong}

    priorities = {
        cue.cue_id: compute_review_priority(
            review_signals_from_consensus_diagnostics(cue.diagnostics, cue.observations)
        )
        for cue in synthetic_cues
    }

    ranked_by_priority = sorted(
        (cue.cue_id for cue in synthetic_cues),
        key=lambda cue_id: priorities[cue_id].score,
        reverse=True,
    )

    rng = random.Random(_SEED + 1)
    random_order = [cue.cue_id for cue in synthetic_cues]
    rng.shuffle(random_order)

    results: dict = {
        "cue_count": _CUE_COUNT,
        "actual_error_count": len(wrong_ids),
        "actual_error_rate": len(wrong_ids) / _CUE_COUNT,
        "top_fraction_recall": {},
    }
    for fraction in _TOP_FRACTIONS:
        priority_recall = _recall_at_fraction(ranked_by_priority, wrong_ids, fraction)
        random_recall = _recall_at_fraction(random_order, wrong_ids, fraction)
        results["top_fraction_recall"][f"top_{int(fraction * 100)}pct"] = {
            "review_priority_recall": priority_recall,
            "random_baseline_recall": random_recall,
            "beats_random": priority_recall > random_recall,
        }

    results["negative_result"] = not all(
        entry["beats_random"] for entry in results["top_fraction_recall"].values()
    )
    return results


if __name__ == "__main__":
    results = run()
    _RESULTS_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    if results["negative_result"]:
        print(
            "\nNEGATIVE RESULT: Review Priority did not beat random review on at "
            "least one top-fraction cut in this synthetic evaluation. Reported "
            "honestly, not tuned away."
        )
