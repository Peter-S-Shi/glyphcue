from dataclasses import replace

from glyphcue.application.review_priority import (
    ReviewSignals,
    compute_review_priority,
    review_signals_from_consensus_diagnostics,
    review_signals_from_multilingual_diagnostics,
)


def test_clean_cue_with_no_signals_has_no_review_flags():
    signals = ReviewSignals(
        cue_id="c1",
        mean_ocr_confidence=0.98,
        had_disagreement=False,
        missing_language_count=0,
        ambiguous_language_count=0,
    )

    priority = compute_review_priority(signals)

    assert priority.score == 0.0
    assert priority.level == "None"
    assert priority.components == ()


def test_low_ocr_confidence_raises_priority_and_is_explained():
    signals = ReviewSignals(
        cue_id="c1",
        mean_ocr_confidence=0.2,
        had_disagreement=False,
        missing_language_count=0,
        ambiguous_language_count=0,
    )

    priority = compute_review_priority(signals)

    assert priority.score > 0.0
    assert len(priority.components) == 1
    component = priority.components[0]
    assert component.name == "ocr_confidence"
    assert "confidence" in component.explanation.lower()


def test_missing_confidence_signal_is_neutral_not_maximally_suspicious():
    # A Path B subtitle-import Cue has no OCR confidence at all -- this
    # must never be silently treated as "confidence 0" (the worst
    # possible reading); it should simply not contribute a component.
    signals = ReviewSignals(
        cue_id="c1",
        mean_ocr_confidence=None,
        had_disagreement=False,
        missing_language_count=0,
        ambiguous_language_count=0,
    )

    priority = compute_review_priority(signals)

    assert priority.score == 0.0
    assert priority.components == ()


def test_cross_frame_disagreement_is_a_named_explainable_component():
    signals = ReviewSignals(
        cue_id="c1",
        mean_ocr_confidence=None,
        had_disagreement=True,
        missing_language_count=0,
        ambiguous_language_count=0,
    )

    priority = compute_review_priority(signals)

    names = [component.name for component in priority.components]
    assert "cross_frame_disagreement" in names
    assert priority.score > 0.0


def test_missing_and_ambiguous_language_layers_each_contribute_their_own_component():
    signals = ReviewSignals(
        cue_id="c1",
        mean_ocr_confidence=None,
        had_disagreement=False,
        missing_language_count=1,
        ambiguous_language_count=1,
    )

    priority = compute_review_priority(signals)

    names = {component.name for component in priority.components}
    assert names == {"missing_language_layer", "ambiguous_language_layer"}


def test_multiple_signals_combine_into_a_higher_priority_than_any_single_signal():
    single = ReviewSignals(
        cue_id="c1", mean_ocr_confidence=None, had_disagreement=True,
        missing_language_count=0, ambiguous_language_count=0,
    )
    combined = ReviewSignals(
        cue_id="c2", mean_ocr_confidence=0.1, had_disagreement=True,
        missing_language_count=1, ambiguous_language_count=0,
    )

    single_priority = compute_review_priority(single)
    combined_priority = compute_review_priority(combined)

    assert len(combined_priority.components) > len(single_priority.components)


def test_score_never_exceeds_one_and_level_buckets_are_the_design_vocabulary():
    worst = ReviewSignals(
        cue_id="c1", mean_ocr_confidence=0.0, had_disagreement=True,
        missing_language_count=3, ambiguous_language_count=3,
    )

    priority = compute_review_priority(worst)

    assert 0.0 <= priority.score <= 1.0
    assert priority.level in {"None", "Low", "Medium", "High"}
    assert priority.level == "High"


def test_review_signals_from_consensus_diagnostics_uses_real_observation_confidence():
    from glyphcue.application.consensus_reconstruction import ConsensusDiagnostics
    from glyphcue.domain.observation import Observation
    from glyphcue.domain.provenance import Provenance, ProvenanceKind

    diagnostics = ConsensusDiagnostics(
        cue_id="cue-1", observation_count=2, distinct_text_count=2,
        agreement_ratio=0.5, had_disagreement=True,
    )
    observations = [
        Observation(
            id="o1", text="a", start_time=0.0, end_time=1.0,
            provenance=Provenance(kind=ProvenanceKind.OCR_ENGINE, source="x"),
            confidence=0.4,
        ),
        Observation(
            id="o2", text="b", start_time=0.0, end_time=1.0,
            provenance=Provenance(kind=ProvenanceKind.OCR_ENGINE, source="x"),
            confidence=0.6,
        ),
    ]

    signals = review_signals_from_consensus_diagnostics(diagnostics, observations)

    assert signals.cue_id == "cue-1"
    assert signals.mean_ocr_confidence == 0.5
    assert signals.had_disagreement is True
    assert signals.missing_language_count == 0
    assert signals.ambiguous_language_count == 0


def test_adding_any_single_nonzero_signal_never_lowers_the_score():
    # ROADMAP M7 correctness invariant: adding evidence of a NEW problem
    # must never make a Cue look LESS worth reviewing. A pure average
    # (the pre-corrective formula) violated this -- e.g. a Cue with only
    # disagreement (score 1.0) would DROP to ~0.5 once a mild low-
    # confidence reading was also added, because averaging a strong
    # signal with a weak one pulls the result down.
    clean = ReviewSignals(
        cue_id="c1", mean_ocr_confidence=None, had_disagreement=False,
        missing_language_count=0, ambiguous_language_count=0,
    )
    clean_score = compute_review_priority(clean).score

    single_signal_variants = [
        replace(clean, mean_ocr_confidence=0.5),
        replace(clean, had_disagreement=True),
        replace(clean, missing_language_count=1),
        replace(clean, ambiguous_language_count=1),
    ]
    for variant in single_signal_variants:
        assert compute_review_priority(variant).score >= clean_score


def test_adding_a_weak_signal_on_top_of_a_strong_one_never_lowers_the_score():
    strong_alone = ReviewSignals(
        cue_id="c1", mean_ocr_confidence=None, had_disagreement=True,
        missing_language_count=0, ambiguous_language_count=0,
    )
    strong_plus_weak = replace(strong_alone, mean_ocr_confidence=0.89)

    strong_alone_score = compute_review_priority(strong_alone).score
    strong_plus_weak_score = compute_review_priority(strong_plus_weak).score

    assert strong_plus_weak_score >= strong_alone_score


def test_score_is_monotonic_non_decreasing_across_every_added_signal_combination():
    import itertools

    toggles = {
        "mean_ocr_confidence": 0.85,  # a real, but weak, below-threshold reading
        "had_disagreement": True,
        "missing_language_count": 1,
        "ambiguous_language_count": 1,
    }
    base = ReviewSignals(
        cue_id="c1", mean_ocr_confidence=None, had_disagreement=False,
        missing_language_count=0, ambiguous_language_count=0,
    )
    names = list(toggles)
    for subset_size in range(len(names)):
        for on_subset in itertools.combinations(names, subset_size):
            for extra in names:
                if extra in on_subset:
                    continue
                smaller = replace(base, **{name: toggles[name] for name in on_subset})
                larger = replace(base, **{name: toggles[name] for name in (*on_subset, extra)})
                assert compute_review_priority(larger).score >= compute_review_priority(smaller).score


def test_review_signals_from_multilingual_diagnostics_counts_missing_and_ambiguous():
    from glyphcue.application.multilingual_reconstruction import MultilingualDiagnostics

    diagnostics = MultilingualDiagnostics(
        cue_id="cue-1",
        languages_expected=("en", "zh", "ja"),
        languages_present=("en",),
        missing_languages=("zh",),
        ambiguous_languages=("ja",),
    )

    signals = review_signals_from_multilingual_diagnostics(diagnostics, observations=[])

    assert signals.missing_language_count == 1
    assert signals.ambiguous_language_count == 1
