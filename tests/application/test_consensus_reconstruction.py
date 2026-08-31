from glyphcue.application.consensus_reconstruction import reconstruct_cues_with_consensus
from glyphcue.application.ocr_evidence_job import STATE_TRIGGER_DETAIL_KEY
from glyphcue.domain.provenance import Provenance, ProvenanceKind

_PROVENANCE = Provenance(kind=ProvenanceKind.OCR_ENGINE, source="PaddleOCR")


def _obs(
    id_,
    text,
    start,
    end=None,
    confidence=None,
    language=None,
    frame_reference=None,
    state_trigger=None,
):
    from glyphcue.domain.observation import Observation

    detail = {STATE_TRIGGER_DETAIL_KEY: state_trigger} if state_trigger else {}
    return Observation(
        id=id_,
        text=text,
        start_time=start,
        end_time=end if end is not None else start + 0.001,
        provenance=Provenance(kind=ProvenanceKind.OCR_ENGINE, source="PaddleOCR", detail=detail),
        language=language,
        confidence=confidence,
        frame_reference=frame_reference,
    )


def test_empty_input_produces_no_cues():
    cues, diagnostics = reconstruct_cues_with_consensus([])

    assert cues == []
    assert diagnostics == []


def test_single_observation_becomes_a_single_cue():
    observations = [_obs("o1", "Hello world", start=1.0)]

    cues, diagnostics = reconstruct_cues_with_consensus(observations)

    assert len(cues) == 1
    cue = cues[0]
    assert cue.language_layers[0].text == "Hello world"
    assert cue.language_layers[0].observation_ids == ("o1",)
    assert len(diagnostics) == 1
    assert diagnostics[0].observation_count == 1


def test_repeated_identical_readings_merge_into_one_cue_with_full_provenance():
    # Three confirmations of the same real subtitle state (e.g. from
    # ChangeTriggeredOcrPolicy's periodic confirmation gap).
    observations = [
        _obs("o1", "Hello world", start=1.0),
        _obs("o2", "Hello world", start=3.0),
        _obs("o3", "Hello world", start=5.0),
    ]

    cues, diagnostics = reconstruct_cues_with_consensus(observations)

    assert len(cues) == 1
    layer = cues[0].language_layers[0]
    assert layer.text == "Hello world"
    # Every supporting observation is kept for provenance, not just the
    # winning one.
    assert layer.observation_ids == ("o1", "o2", "o3")
    assert diagnostics[0].agreement_ratio == 1.0
    assert diagnostics[0].had_disagreement is False


def test_two_distinct_states_produce_two_cues_with_state_transition_timing():
    observations = [
        _obs("o1", "The quick brown fox", start=1.0, end=1.001),
        _obs("o2", "Bright orange sunsets glow", start=4.0, end=4.001),
    ]

    cues, _diagnostics = reconstruct_cues_with_consensus(observations)

    assert len(cues) == 2
    first, second = cues
    assert first.language_layers[0].text == "The quick brown fox"
    assert second.language_layers[0].text == "Bright orange sunsets glow"
    # The first Cue's end is the moment the second state was confirmed
    # (state-transition semantics), not just its own last observation's
    # end_time (1.001) -- that would understate real on-screen duration.
    assert first.start_time == 1.0
    assert first.end_time == 4.0
    # The last Cue has no known "next" boundary, so it falls back to its
    # own last observation's end_time.
    assert second.start_time == 4.0
    assert second.end_time == 4.001


def test_majority_vote_picks_the_more_common_reading_over_a_noisy_outlier():
    # Two clean readings and one OCR-noise misread of the same real state.
    observations = [
        _obs("o1", "Hello world", start=1.0),
        _obs("o2", "Hallo world", start=2.0),  # noisy misread
        _obs("o3", "Hello world", start=3.0),
    ]

    cues, diagnostics = reconstruct_cues_with_consensus(observations)

    assert len(cues) == 1
    assert cues[0].language_layers[0].text == "Hello world"
    # The noisy observation is still kept for provenance.
    assert cues[0].language_layers[0].observation_ids == ("o1", "o2", "o3")
    assert diagnostics[0].distinct_text_count == 2
    assert diagnostics[0].had_disagreement is True
    assert diagnostics[0].agreement_ratio == 2 / 3


def test_tied_vote_is_broken_by_higher_confidence():
    observations = [
        _obs("o1", "Reading A", start=1.0, confidence=0.6),
        _obs("o2", "Reading B", start=2.0, confidence=0.95),
    ]
    # Force these two into one run despite differing text, by using a
    # low similarity_threshold that treats them as the same state.
    cues, _diagnostics = reconstruct_cues_with_consensus(observations, similarity_threshold=0.0)

    assert len(cues) == 1
    assert cues[0].language_layers[0].text == "Reading B"


def test_cjk_grouping_and_voting_do_not_use_whitespace_tokenization():
    observations = [
        _obs("o1", "今天天气非常好", start=1.0),
        _obs("o2", "今天天气非常坏", start=2.0),  # one-character OCR noise
        _obs("o3", "今天天气非常好", start=3.0),
    ]

    cues, diagnostics = reconstruct_cues_with_consensus(observations)

    assert len(cues) == 1
    assert cues[0].language_layers[0].text == "今天天气非常好"
    assert diagnostics[0].had_disagreement is True


def test_japanese_state_change_is_detected_as_a_new_cue():
    observations = [
        _obs("o1", "今日はとても良い天気ですね", start=1.0, end=1.001),
        _obs("o2", "明日は雨が降りそうです", start=5.0, end=5.001),
    ]

    cues, _diagnostics = reconstruct_cues_with_consensus(observations)

    assert len(cues) == 2
    assert cues[0].language_layers[0].text == "今日はとても良い天気ですね"
    assert cues[1].language_layers[0].text == "明日は雨が降りそうです"
    assert cues[0].end_time == 5.0


def test_language_field_is_decided_by_majority_vote_with_und_fallback():
    observations = [
        _obs("o1", "Hello", start=1.0, language="en"),
        _obs("o2", "Hello", start=2.0, language="en"),
        _obs("o3", "Hello", start=3.0, language=None),
    ]

    cues, _diagnostics = reconstruct_cues_with_consensus(observations)

    assert cues[0].language_layers[0].language == "en"


def test_language_tie_break_does_not_crash_when_some_observations_have_no_language():
    # Regression: the tie-break path used to index into a `values` list
    # that had already been filtered to drop None languages, while
    # iterating `enumerate(run)` (unfiltered) -- a length/index
    # mismatch that crashed (or silently misaligned) as soon as a tie
    # occurred with any None-language observation present.
    observations = [
        _obs("o1", "Hello", start=1.0, language="en", confidence=0.5),
        _obs("o2", "Hello", start=2.0, language=None, confidence=0.99),
        _obs("o3", "Hello", start=3.0, language="zh", confidence=0.9),
    ]

    cues, _diagnostics = reconstruct_cues_with_consensus(observations)

    # "en" and "zh" are tied 1-1 (None is excluded from voting); the
    # tie is broken by confidence among the tied candidates -- "zh" (0.9)
    # beats "en" (0.5). The None-language observation is not a candidate.
    assert cues[0].language_layers[0].language == "zh"


def test_language_falls_back_to_und_when_no_observation_reports_one():
    observations = [_obs("o1", "Hello", start=1.0, language=None)]

    cues, _diagnostics = reconstruct_cues_with_consensus(observations)

    assert cues[0].language_layers[0].language == "und"


def test_reconstruction_is_deterministic_across_repeated_runs():
    observations = [
        _obs("o1", "Hello world", start=1.0),
        _obs("o2", "Hallo world", start=2.0),
        _obs("o3", "Hello world", start=3.0),
        _obs("o4", "Second state", start=6.0, end=6.001),
    ]

    first_cues, first_diag = reconstruct_cues_with_consensus(observations)
    second_cues, second_diag = reconstruct_cues_with_consensus(observations)

    assert first_cues == second_cues
    assert first_diag == second_diag


def test_input_order_does_not_affect_the_result():
    ordered = [
        _obs("o1", "Hello world", start=1.0),
        _obs("o2", "Hello world", start=2.0),
        _obs("o3", "Second state", start=6.0, end=6.001),
    ]
    shuffled = [ordered[2], ordered[0], ordered[1]]

    cues_from_ordered, _ = reconstruct_cues_with_consensus(ordered)
    cues_from_shuffled, _ = reconstruct_cues_with_consensus(shuffled)

    assert cues_from_ordered == cues_from_shuffled


def test_same_frame_regions_are_aggregated_before_cross_frame_consensus():
    # Two regions of ONE frame (e.g. a two-line subtitle detected as two
    # boxes) must become one reading/one Cue, not two sequential states,
    # even though "Line one" and "Line two" are not textually similar.
    observations = [
        _obs("o1", "Line one", start=1.0, frame_reference="v.mp4@1.000000s"),
        _obs("o2", "Line two", start=1.0, frame_reference="v.mp4@1.000000s"),
    ]

    cues, _diagnostics = reconstruct_cues_with_consensus(observations)

    assert len(cues) == 1
    assert cues[0].language_layers[0].text == "Line oneLine two"
    # Full provenance to both original region observations is kept.
    assert cues[0].language_layers[0].observation_ids == ("o1", "o2")


def test_detected_change_forces_a_new_cue_even_when_text_is_very_similar():
    # "Hello world today" -> "Hello world today!" is well above the
    # 0.5 similarity threshold, so pairwise text similarity alone would
    # wrongly merge these -- but the second observation carries real
    # M4 evidence that a visual change was actually detected, which
    # must win.
    observations = [
        _obs("o1", "Hello world today", start=1.0, end=1.001, state_trigger="first_frame"),
        _obs(
            "o2", "Hello world today!", start=4.0, end=4.001, state_trigger="change_detected"
        ),
    ]

    cues, _diagnostics = reconstruct_cues_with_consensus(observations)

    assert len(cues) == 2
    assert cues[0].language_layers[0].text == "Hello world today"
    assert cues[1].language_layers[0].text == "Hello world today!"


def test_change_detected_with_an_unchanged_reading_does_not_split():
    # ChangeTriggeredOcrPolicy's change_detected is only a CANDIDATE
    # boundary from a cheap visual detector -- e.g. a moving/flickering
    # background behind static burned-in text can cross the pixel-diff
    # threshold without the subtitle itself changing. If the OCR
    # reading stays exactly the same, that candidate must not create a
    # duplicate Cue.
    observations = [
        _obs("o1", "Hello world", start=1.0, state_trigger="first_frame"),
        _obs("o2", "Hello world", start=2.0, state_trigger="change_detected"),
        _obs("o3", "Hello world", start=3.0, state_trigger="change_detected"),
    ]

    cues, _diagnostics = reconstruct_cues_with_consensus(observations)

    assert len(cues) == 1
    assert cues[0].language_layers[0].text == "Hello world"


def test_change_detected_candidate_rejected_when_next_evidence_reverts():
    # A momentary garbage misread coincides with a change_detected
    # candidate, but the very next reading reverts to the real,
    # unchanged state -- the candidate is a false positive and must be
    # absorbed as an outlier, not promoted to its own Cue.
    observations = [
        _obs("o1", "Hello world", start=1.0, state_trigger="first_frame"),
        _obs("o2", "###???", start=2.0, state_trigger="change_detected"),
        _obs("o3", "Hello world", start=3.0, state_trigger="periodic_confirmation"),
    ]

    cues, diagnostics = reconstruct_cues_with_consensus(observations)

    assert len(cues) == 1
    assert cues[0].language_layers[0].text == "Hello world"
    assert cues[0].language_layers[0].observation_ids == ("o1", "o2", "o3")
    assert diagnostics[0].had_disagreement is True


def test_change_detected_candidate_confirmed_when_next_evidence_supports_it():
    # A real A->B transition, confirmed because the reading AFTER the
    # candidate continues to support B rather than reverting to A.
    observations = [
        _obs("o1", "Hello world today", start=1.0, state_trigger="first_frame"),
        _obs("o2", "Hello world today!", start=4.0, state_trigger="change_detected"),
        _obs("o3", "Hello world today!", start=6.0, state_trigger="periodic_confirmation"),
    ]

    cues, _diagnostics = reconstruct_cues_with_consensus(observations)

    assert len(cues) == 2
    assert cues[0].language_layers[0].text == "Hello world today"
    assert cues[1].language_layers[0].text == "Hello world today!"
    assert cues[1].language_layers[0].observation_ids == ("o2", "o3")


def test_periodic_confirmation_of_the_same_state_still_uses_similarity_voting():
    # A noisy outlier from a periodic-confirmation OCR call (state
    # hasn't visually changed) must still be absorbed by consensus, not
    # treated as a new state just because it's a distinct reading.
    observations = [
        _obs("o1", "Hello world", start=1.0, state_trigger="first_frame"),
        _obs("o2", "Hallo world", start=3.0, state_trigger="periodic_confirmation"),
        _obs("o3", "Hello world", start=5.0, state_trigger="periodic_confirmation"),
    ]

    cues, diagnostics = reconstruct_cues_with_consensus(observations)

    assert len(cues) == 1
    assert cues[0].language_layers[0].text == "Hello world"
    assert diagnostics[0].had_disagreement is True


def test_blank_marker_ends_the_preceding_cue_without_becoming_a_cue_itself():
    # Texts are deliberately dissimilar (not just different): the blank
    # must be confirmed by subsequent evidence that does NOT support the
    # old reading -- see test_a_single_ocr_empty_read_does_not_end_a_cue
    # for the case where it should be rejected instead.
    observations = [
        _obs("o1", "The quick brown fox", start=1.0, end=1.001),
        _obs("o2", "", start=3.0, end=3.001),  # blank candidate
        _obs("o3", "Bright orange sunsets glow", start=5.0, end=5.001),
    ]

    cues, _diagnostics = reconstruct_cues_with_consensus(observations)

    assert len(cues) == 2
    assert [cue.language_layers[0].text for cue in cues] == [
        "The quick brown fox",
        "Bright orange sunsets glow",
    ]
    # The first Cue ends at the blank marker's start_time (honest
    # transition-to-blank evidence), not at the second subtitle's
    # start_time -- which would wrongly stretch it across the blank gap.
    assert cues[0].end_time == 3.0
    assert cues[1].start_time == 5.0


def test_a_single_ocr_empty_read_does_not_end_a_cue():
    # A→one empty→A: the blank candidate is rejected once the very next
    # reading reverts to the same real state -- this is an OCR-empty
    # glitch (e.g. a momentary detection miss), not a real blank gap.
    observations = [
        _obs("o1", "Subtitle stays here", start=1.0, end=1.001),
        _obs("o2", "", start=3.0, end=3.001),  # OCR-empty candidate, not confirmed
        _obs("o3", "Subtitle stays here", start=5.0, end=5.001),
    ]

    cues, diagnostics = reconstruct_cues_with_consensus(observations)

    assert len(cues) == 1
    assert cues[0].language_layers[0].text == "Subtitle stays here"
    # The rejected blank candidate is still kept for provenance.
    assert cues[0].language_layers[0].observation_ids == ("o1", "o2", "o3")


def test_sustained_blank_evidence_confirms_a_real_gap_backdated_to_the_first_candidate():
    observations = [
        _obs("o1", "The quick brown fox", start=1.0, end=1.001),
        _obs("o2", "", start=3.0, end=3.001),  # first blank candidate
        _obs("o3", "", start=5.0, end=5.001),  # sustained blank evidence
        _obs("o4", "Bright orange sunsets glow", start=7.0, end=7.001),
    ]

    cues, _diagnostics = reconstruct_cues_with_consensus(observations)

    assert [cue.language_layers[0].text for cue in cues] == [
        "The quick brown fox",
        "Bright orange sunsets glow",
    ]
    # Boundary backdates to the FIRST blank candidate (o2 at 3.0), not
    # the last one before confirmation (o3 at 5.0).
    assert cues[0].end_time == 3.0
    assert cues[1].start_time == 7.0


def test_a_blank_marker_with_nothing_before_it_produces_no_cue():
    observations = [_obs("o1", "", start=1.0, end=1.001)]

    cues, diagnostics = reconstruct_cues_with_consensus(observations)

    assert cues == []
    assert diagnostics == []


def test_final_cue_uses_the_supplied_processing_end_time_not_a_1ms_instant():
    observations = [_obs("o1", "Only subtitle", start=1.0, end=1.001)]

    cues, _diagnostics = reconstruct_cues_with_consensus(observations, processing_end_time=9.5)

    assert len(cues) == 1
    assert cues[0].start_time == 1.0
    assert cues[0].end_time == 9.5


def test_final_cue_without_processing_end_time_falls_back_to_its_last_observation():
    # Documented, honest fallback when the caller has no better
    # evidence available -- not a silent lie, just the least-bad option.
    observations = [_obs("o1", "Only subtitle", start=1.0, end=1.001)]

    cues, _diagnostics = reconstruct_cues_with_consensus(observations)

    assert cues[0].end_time == 1.001
