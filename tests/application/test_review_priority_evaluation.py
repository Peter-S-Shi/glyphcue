"""Targeted regression for the Review Priority evaluation's corrected
methodology (`benchmarks/review_priority/run_evaluation.py`): ground
truth is defined independently, observations are noisy but not labeled,
and "is this Cue's reconstruction wrong" is derived only by actually
calling the real production reconstruction seam and comparing its
output to ground truth -- never assigned up front.
"""

import random

from benchmarks.review_priority.run_evaluation import (
    _ground_truth_text,
    _make_observations_for_cue,
)
from glyphcue.application.consensus_reconstruction import reconstruct_cues_with_consensus


def test_all_clean_readings_reconstruct_exactly_to_ground_truth():
    # Asserts the real production behavior the evaluation script relies
    # on: when every reading is a clean, exact capture of the ground
    # truth, the real consensus vote recovers it exactly, with no
    # disagreement -- this is the baseline the noisy-reading case is
    # measured against.
    ground_truth = _ground_truth_text(0)
    observations = []
    from glyphcue.domain.observation import Observation
    from glyphcue.domain.provenance import Provenance, ProvenanceKind

    for index in range(6):
        observations.append(
            Observation(
                id=f"cue-0-obs-{index}",
                text=ground_truth,
                start_time=index * 1.0,
                end_time=index * 1.0 + 0.9,
                provenance=Provenance(kind=ProvenanceKind.OCR_ENGINE, source="synthetic"),
                confidence=0.95,
            )
        )

    cues, diagnostics = reconstruct_cues_with_consensus(observations)

    assert len(cues) == 1
    assert cues[0].language_layers[0].text == ground_truth
    assert diagnostics[0].had_disagreement is False


def test_ground_truth_texts_are_distinct_and_dissimilar_across_cues():
    # A regression for the earlier corpus-generation bug where a shared
    # literal template ("synthetic line {index} ...") gave every Cue's
    # ground truth a long common prefix, which risked the real
    # reconstruction seam's similarity-based grouping merging two
    # different synthetic Cues into one run.
    from glyphcue.application.text_similarity import character_similarity

    texts = [_ground_truth_text(index) for index in range(20)]
    assert len(set(texts)) == len(texts)
    for i in range(len(texts) - 1):
        assert character_similarity(texts[i], texts[i + 1]) < 0.5


def test_make_observations_for_cue_returns_only_observations_no_correctness_label():
    # `_make_observations_for_cue` must only ever return a list of
    # Observations -- it has no business deciding or returning whether
    # the eventual reconstruction will be right or wrong (that is
    # derived later, only from the real reconstruction seam's own
    # output being compared to ground truth).
    ground_truth = _ground_truth_text(1)
    rng = random.Random("seed")

    result = _make_observations_for_cue(rng, 1, ground_truth)

    assert isinstance(result, list)
    assert all(type(observation).__name__ == "Observation" for observation in result)
