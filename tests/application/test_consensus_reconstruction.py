from glyphcue.application.consensus_reconstruction import reconstruct_cues_with_consensus
from glyphcue.domain.provenance import Provenance, ProvenanceKind

_PROVENANCE = Provenance(kind=ProvenanceKind.OCR_ENGINE, source="PaddleOCR")


def _obs(id_, text, start, end=None, confidence=None, language=None):
    from glyphcue.domain.observation import Observation

    return Observation(
        id=id_,
        text=text,
        start_time=start,
        end_time=end if end is not None else start + 0.001,
        provenance=_PROVENANCE,
        language=language,
        confidence=confidence,
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
