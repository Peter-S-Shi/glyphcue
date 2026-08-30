from glyphcue.application.reconstruction import reconstruct_cues
from glyphcue.domain.observation import Observation
from glyphcue.domain.provenance import Provenance, ProvenanceKind


def _observation(id_: str, text: str, start: float, end: float, language=None) -> Observation:
    return Observation(
        id=id_,
        text=text,
        start_time=start,
        end_time=end,
        provenance=Provenance(kind=ProvenanceKind.SUBTITLE_IMPORT, source="input.srt"),
        language=language,
    )


def test_normal_non_overlapping_observations_are_left_unchanged():
    observations = [
        _observation("o1", "First complete sentence.", 0.0, 2.0),
        _observation("o2", "Second complete sentence.", 2.1, 4.0),
        _observation("o3", "Third complete sentence.", 4.1, 6.0),
    ]

    cues = reconstruct_cues(observations)

    assert len(cues) == 3
    assert [cue.language_layers[0].text for cue in cues] == [
        "First complete sentence.",
        "Second complete sentence.",
        "Third complete sentence.",
    ]
    assert [(cue.start_time, cue.end_time) for cue in cues] == [
        (0.0, 2.0),
        (2.1, 4.0),
        (4.1, 6.0),
    ]


def test_growing_window_rolling_caption_merges_into_one_cue():
    observations = [
        _observation("o1", "Hello", 0.0, 2.0),
        _observation("o2", "Hello world", 1.0, 4.0),
        _observation("o3", "Hello world, how are you", 3.0, 6.0),
    ]

    cues = reconstruct_cues(observations)

    assert len(cues) == 1
    cue = cues[0]
    assert cue.start_time == 0.0
    assert cue.end_time == 6.0
    assert cue.language_layers[0].text == "Hello world, how are you"
    assert cue.language_layers[0].observation_ids == ("o1", "o2", "o3")


def test_sliding_overlap_caption_merges_via_partial_overlap():
    observations = [
        _observation("o1", "the quick brown fox", 0.0, 2.0),
        _observation("o2", "brown fox jumps over", 1.5, 4.0),
        _observation("o3", "jumps over the lazy dog", 3.5, 6.0),
    ]

    cues = reconstruct_cues(observations)

    assert len(cues) == 1
    assert cues[0].language_layers[0].text == "the quick brown fox jumps over the lazy dog"


def test_overlapping_timing_without_enough_evidence_is_not_merged():
    observations = [
        _observation("o1", "Speaker A says something long", 0.0, 5.0),
        _observation("o2", "Speaker B interjects briefly", 1.0, 3.0),
    ]

    cues = reconstruct_cues(observations)

    assert len(cues) == 2
    assert cues[0].language_layers[0].text == "Speaker A says something long"
    assert cues[1].language_layers[0].text == "Speaker B interjects briefly"
    assert (cues[0].start_time, cues[0].end_time) == (0.0, 5.0)
    assert (cues[1].start_time, cues[1].end_time) == (1.0, 3.0)


def test_three_overlapping_but_textually_unrelated_cues_are_not_merged():
    # Regression: the old whole-file heuristic only required a majority
    # of consecutive pairs to overlap in TIME, with no requirement that
    # the text actually continue from one cue to the next. That could
    # wrongly merge three or more genuinely unrelated overlapping cues
    # (e.g. simultaneous dialogue) into one garbled Cue.
    observations = [
        _observation("o1", "Alpha team reports in", 0.0, 4.0),
        _observation("o2", "Bravo squad moving north", 1.0, 5.0),
        _observation("o3", "Charlie holding position", 2.0, 6.0),
    ]

    cues = reconstruct_cues(observations)

    assert len(cues) == 3
    assert [cue.language_layers[0].text for cue in cues] == [
        "Alpha team reports in",
        "Bravo squad moving north",
        "Charlie holding position",
    ]


def test_rolling_run_in_the_middle_of_a_file_is_isolated_from_normal_neighbors():
    # Regression: the old whole-file heuristic decided rolling/not-rolling
    # for the entire observation sequence at once, so it could not handle
    # a mixed file where only a contiguous middle segment is rolling.
    observations = [
        _observation("o1", "First complete sentence.", 0.0, 2.0),
        _observation("o2", "Hello", 3.0, 5.0),
        _observation("o3", "Hello world", 4.0, 7.0),
        _observation("o4", "Hello world, how are you", 6.0, 9.0),
        _observation("o5", "Third complete sentence.", 10.0, 12.0),
    ]

    cues = reconstruct_cues(observations)

    assert len(cues) == 3
    assert cues[0].language_layers[0].text == "First complete sentence."
    assert (cues[0].start_time, cues[0].end_time) == (0.0, 2.0)

    assert cues[1].language_layers[0].text == "Hello world, how are you"
    assert (cues[1].start_time, cues[1].end_time) == (3.0, 9.0)
    assert cues[1].language_layers[0].observation_ids == ("o2", "o3", "o4")

    assert cues[2].language_layers[0].text == "Third complete sentence."
    assert (cues[2].start_time, cues[2].end_time) == (10.0, 12.0)


def test_cjk_growing_window_rolling_merges_via_character_overlap_not_whitespace_tokens():
    # Japanese has no spaces between words. A whitespace-`.split()`-based
    # overlap detector would see each observation as a single opaque
    # token with no shared tokens between observations, and would fail to
    # dedupe -- this fixture only passes with character-level overlap.
    observations = [
        _observation("o1", "こんにちは", 0.0, 2.0, language="ja"),
        _observation("o2", "こんにちは世界", 1.0, 4.0, language="ja"),
        _observation("o3", "こんにちは世界、ようこそ", 3.0, 6.0, language="ja"),
    ]

    cues = reconstruct_cues(observations)

    assert len(cues) == 1
    layer = cues[0].language_layers[0]
    assert layer.language == "ja"
    assert layer.text == "こんにちは世界、ようこそ"
