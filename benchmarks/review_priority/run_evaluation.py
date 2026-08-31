"""Milestone 7 Review Priority evaluation: does ranking Cues by
`compute_review_priority`'s score actually surface more real
reconstruction errors than reviewing the same number of Cues in random
order?

This is a synthetic, constructed evaluation, not a claim about real
subtitle error rates -- no scraped video, subtitle, or transcript data is
used anywhere.

Corrective methodology (this replaces an earlier version of this script
that generated a ground-truth "is_wrong" label FIRST and then derived
evidence quality FROM that label -- a label leak: the evaluation was
partly measuring its own construction, not the real ranking mechanism).
This version instead:

1. Defines an independent ground-truth Cue text corpus (synthetic
   sentences, not derived from anything else).
2. For each ground-truth Cue, generates several noisy Observations --
   OCR-style character corruption and a confidence reading -- controlled
   by a per-Cue "noise level" drawn independently of any correctness
   label (no `is_wrong` exists yet at this point).
3. Feeds ALL of those Observations through the real, unmodified
   production reconstruction seam, `reconstruct_cues_with_consensus`
   (`glyphcue.application.consensus_reconstruction`) -- the same
   function Path A's OCR pipeline calls -- to get back real
   reconstructed Cues plus real `ConsensusDiagnostics`.
4. Derives `is_error` AFTER the fact, automatically, by comparing each
   reconstructed Cue's winning text against the ground-truth text for
   that Cue -- never hand-labeled, never chosen to make the ranking look
   good.
5. Computes Review Priority from the SAME real diagnostics and real
   Observations the reconstruction run produced, via the real
   `compute_review_priority` + `review_signals_from_consensus_diagnostics`.
6. Compares top-N/top-percentile error recall against MULTIPLE seeded
   random-order baselines (not just one shuffle), averaged, for a more
   stable comparison.

If ranking does not outperform the random baseline here, that is
reported honestly in the output -- this script does not tune itself
until the numbers look good.

Run manually:
    python -m benchmarks.review_priority.run_evaluation
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from glyphcue.application.consensus_reconstruction import reconstruct_cues_with_consensus
from glyphcue.application.review_priority import (
    compute_review_priority,
    review_signals_from_consensus_diagnostics,
)
from glyphcue.domain.observation import Observation
from glyphcue.domain.provenance import Provenance, ProvenanceKind

_RESULTS_PATH = Path(__file__).parent / "evaluation_results.json"
_CUE_COUNT = 200
_SEED = 20260831
_RANDOM_BASELINE_TRIAL_COUNT = 20
_TOP_FRACTIONS = (0.1, 0.2, 0.3)
_OBSERVATIONS_PER_CUE = 6
"""M5's real reconstruction seam is a MULTI-frame consensus vote over
exact text matches (`consensus_value`, a plain `Counter` over each
reading's raw text) -- with too few readings per Cue, one lone
corrupted reading looks the same to that vote as a real disagreement
between two otherwise-clean majorities, which does not reflect how the
production OCR pipeline actually samples a Cue (many repeated frames,
not two or three). 6 keeps the corpus small enough to stay a synthetic,
non-realistic evaluation while giving the real disagreement signal a
fair chance to distinguish "one noisy outlier among an otherwise
unanimous, correct majority" from "no real majority at all.\""""
_CUE_TIME_SPAN_SECONDS = 10.0
"""Ground-truth Cues are laid out back-to-back on a synthetic timeline,
far enough apart (relative to each Cue's own ~1s observation spread)
that the real reconstruction seam's own similarity-based state-run
grouping (see `group_into_state_runs`) does not accidentally merge two
different synthetic Cues, or split one Cue's own noisy readings into
two -- this evaluation is about ranking, not about re-testing M5's own
grouping algorithm."""


def _ground_truth_text(index: int) -> str:
    """An independent, synthetic (non-copyrighted, non-readable-sentence)
    ground-truth reading for Cue `index`: a purely random 24-letter
    string, seeded only from the index -- never from any correctness
    label (there is no such label yet at this point in the pipeline).
    Deliberately NOT built from a shared template/prefix (an earlier
    version used "synthetic line {index} ...", which shares a long
    literal prefix across every Cue) -- a shared prefix risks the real
    reconstruction seam's own similarity-based state-run grouping
    (`group_into_state_runs`) mistaking two different synthetic Cues'
    readings for continuations of the same state, which would corrupt
    this evaluation's own Cue boundaries, not just its text content."""
    alphabet = "abcdefghijklmnopqrstuvwxyz"
    local_rng = random.Random(f"ground-truth-{index}")
    return "".join(local_rng.choice(alphabet) for _ in range(24))


def _corrupt_text(rng: random.Random, text: str, corruption_rate: float) -> str:
    """A crude OCR-noise stand-in: each character independently has
    `corruption_rate` odds of being replaced by a random lowercase
    letter. Purely mechanical, no awareness of what the "correct"
    reconstruction should be."""
    if corruption_rate <= 0.0:
        return text
    alphabet = "abcdefghijklmnopqrstuvwxyz"
    chars = list(text)
    for index, char in enumerate(chars):
        if char.isalpha() and rng.random() < corruption_rate:
            chars[index] = rng.choice(alphabet)
    return "".join(chars)


def _make_observations_for_cue(
    rng: random.Random, cue_index: int, ground_truth_text: str
) -> list[Observation]:
    """Independently draws a per-Cue noise level (NOT a correctness
    label -- nothing here knows or decides whether the eventual
    reconstruction will be right or wrong) and generates
    `_OBSERVATIONS_PER_CUE` readings from it. Each reading is either a
    clean, exact capture of the ground truth or an independently
    corrupted one; `noise_level` only sets the ODDS of a clean reading,
    never the reconstruction outcome directly -- whether the real
    majority vote (`reconstruct_cues_with_consensus`, exact-text-based)
    actually recovers the ground truth from these readings is left
    entirely to the real algorithm to decide."""
    noise_level = rng.random()
    base_time = cue_index * _CUE_TIME_SPAN_SECONDS
    observations = []
    for reading_index in range(_OBSERVATIONS_PER_CUE):
        is_clean_reading = rng.random() >= noise_level
        if is_clean_reading:
            text = ground_truth_text
            confidence = rng.uniform(0.85, 1.0)
        else:
            text = _corrupt_text(rng, ground_truth_text, corruption_rate=rng.uniform(0.05, 0.3))
            confidence = rng.uniform(0.2, 0.75)
        start = base_time + reading_index * 1.0
        observations.append(
            Observation(
                id=f"cue-{cue_index}-obs-{reading_index}",
                text=text,
                start_time=start,
                end_time=start + 0.9,
                provenance=Provenance(kind=ProvenanceKind.OCR_ENGINE, source="synthetic"),
                confidence=confidence,
            )
        )
    return observations


def _recall_at_fraction(ranked_ids: list[str], wrong_ids: set[str], fraction: float) -> float:
    if not wrong_ids:
        return 0.0
    top_n = max(1, round(len(ranked_ids) * fraction))
    reviewed = set(ranked_ids[:top_n])
    captured = len(reviewed & wrong_ids)
    return captured / len(wrong_ids)


def run() -> dict:
    generation_rng = random.Random(_SEED)

    ground_truth_by_index = {index: _ground_truth_text(index) for index in range(_CUE_COUNT)}
    all_observations: list[Observation] = []
    for index in range(_CUE_COUNT):
        all_observations.extend(
            _make_observations_for_cue(generation_rng, index, ground_truth_by_index[index])
        )

    # The real, unmodified production reconstruction seam -- the exact
    # function Path A's OCR pipeline calls -- decides the winning text
    # and produces real ConsensusDiagnostics. Nothing about this call is
    # benchmark-specific.
    reconstructed_cues, diagnostics_list = reconstruct_cues_with_consensus(all_observations)

    observations_by_id = {observation.id: observation for observation in all_observations}

    # `is_error` is derived AFTER reconstruction, automatically, by
    # comparing the real reconstructed text against the independent
    # ground truth for the Cue whose observations produced it -- never
    # hand-assigned.
    priorities = {}
    wrong_ids: set[str] = set()
    for cue, diagnostics in zip(reconstructed_cues, diagnostics_list):
        source_cue_index = int(cue.language_layers[0].observation_ids[0].split("-")[1])
        ground_truth_text = ground_truth_by_index[source_cue_index]
        if cue.language_layers[0].text != ground_truth_text:
            wrong_ids.add(cue.id)

        cue_observations = [
            observations_by_id[observation_id]
            for observation_id in cue.language_layers[0].observation_ids
            if observation_id in observations_by_id
        ]
        priorities[cue.id] = compute_review_priority(
            review_signals_from_consensus_diagnostics(diagnostics, cue_observations)
        )

    all_ids = [cue.id for cue in reconstructed_cues]
    ranked_by_priority = sorted(all_ids, key=lambda cue_id: priorities[cue_id].score, reverse=True)

    random_baseline_rng = random.Random(_SEED + 1)
    random_recalls: dict[str, list[float]] = {
        f"top_{int(fraction * 100)}pct": [] for fraction in _TOP_FRACTIONS
    }
    for _trial in range(_RANDOM_BASELINE_TRIAL_COUNT):
        shuffled = list(all_ids)
        random_baseline_rng.shuffle(shuffled)
        for fraction in _TOP_FRACTIONS:
            key = f"top_{int(fraction * 100)}pct"
            random_recalls[key].append(_recall_at_fraction(shuffled, wrong_ids, fraction))

    results: dict = {
        "cue_count": len(reconstructed_cues),
        "actual_error_count": len(wrong_ids),
        "actual_error_rate": len(wrong_ids) / len(reconstructed_cues) if reconstructed_cues else 0.0,
        "random_baseline_trial_count": _RANDOM_BASELINE_TRIAL_COUNT,
        "top_fraction_recall": {},
    }
    for fraction in _TOP_FRACTIONS:
        key = f"top_{int(fraction * 100)}pct"
        priority_recall = _recall_at_fraction(ranked_by_priority, wrong_ids, fraction)
        mean_random_recall = sum(random_recalls[key]) / len(random_recalls[key])
        results["top_fraction_recall"][key] = {
            "review_priority_recall": priority_recall,
            "mean_random_baseline_recall": mean_random_recall,
            "beats_random": priority_recall > mean_random_recall,
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
            "\nNEGATIVE RESULT: Review Priority did not beat the random baseline on "
            "at least one top-fraction cut in this synthetic evaluation. Reported "
            "honestly, not tuned away."
        )
