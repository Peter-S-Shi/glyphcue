"""Milestone 8 ground-truth fixture matrix for Path B's deepened,
diagnostics-first reconstruction (`reconstruct_cues_with_diagnostics`).

Each fixture is a deterministic, hand-authored (non-scraped) Observation
sequence with an independently-known correct outcome -- both the
expected Cue text/timing AND the expected diagnostic classification.
Diagnosis comes first: source ordering is never silently discarded by
sorting, and every merge/non-merge decision must be explainable via a
named diagnostic, not just "it happened to work out."
"""

from glyphcue.application.reconstruction import (
    PathBDiagnostics,
    reconstruct_cues,
    reconstruct_cues_with_diagnostics,
)
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


def _no_flags(diagnostics: PathBDiagnostics) -> bool:
    return not any(
        (
            diagnostics.source_order_issue,
            diagnostics.rolling_growth,
            diagnostics.sliding_overlap,
            diagnostics.repetition_collapsed,
            diagnostics.timing_collision,
            diagnostics.segmentation_ambiguous,
        )
    )


# -- Clean preservation: English and CJK ------------------------------------


def test_clean_english_1_to_1_preservation_has_no_diagnostic_flags():
    observations = [
        _observation("o1", "First complete sentence.", 0.0, 2.0),
        _observation("o2", "Second complete sentence.", 2.1, 4.0),
    ]

    cues, diagnostics = reconstruct_cues_with_diagnostics(observations)

    assert [cue.language_layers[0].text for cue in cues] == [
        "First complete sentence.",
        "Second complete sentence.",
    ]
    assert all(_no_flags(d) for d in diagnostics)


def test_clean_cjk_1_to_1_preservation_has_no_diagnostic_flags():
    observations = [
        _observation("o1", "第一句话。", 0.0, 2.0, language="zh"),
        _observation("o2", "第二句话。", 2.1, 4.0, language="zh"),
    ]

    cues, diagnostics = reconstruct_cues_with_diagnostics(observations)

    assert [cue.language_layers[0].text for cue in cues] == ["第一句话。", "第二句话。"]
    assert all(_no_flags(d) for d in diagnostics)


# -- Rolling growth -----------------------------------------------------------


def test_english_growing_window_is_flagged_rolling_growth():
    observations = [
        _observation("o1", "Hello", 0.0, 2.0),
        _observation("o2", "Hello world", 1.0, 4.0),
        _observation("o3", "Hello world, how are you", 3.0, 6.0),
    ]

    cues, diagnostics = reconstruct_cues_with_diagnostics(observations)

    assert len(cues) == 1
    assert cues[0].language_layers[0].text == "Hello world, how are you"
    assert diagnostics[0].rolling_growth is True
    assert diagnostics[0].sliding_overlap is False
    assert diagnostics[0].repetition_collapsed is False


def test_cjk_growing_window_is_flagged_rolling_growth():
    observations = [
        _observation("o1", "こんにちは", 0.0, 2.0, language="ja"),
        _observation("o2", "こんにちは世界", 1.0, 4.0, language="ja"),
        _observation("o3", "こんにちは世界、ようこそ", 3.0, 6.0, language="ja"),
    ]

    cues, diagnostics = reconstruct_cues_with_diagnostics(observations)

    assert len(cues) == 1
    assert cues[0].language_layers[0].text == "こんにちは世界、ようこそ"
    assert diagnostics[0].rolling_growth is True


# -- Sliding overlap -----------------------------------------------------------


def test_sliding_overlap_is_flagged_distinctly_from_rolling_growth():
    observations = [
        _observation("o1", "the quick brown fox", 0.0, 2.0),
        _observation("o2", "brown fox jumps over", 1.5, 4.0),
        _observation("o3", "jumps over the lazy dog", 3.5, 6.0),
    ]

    cues, diagnostics = reconstruct_cues_with_diagnostics(observations)

    assert len(cues) == 1
    assert cues[0].language_layers[0].text == "the quick brown fox jumps over the lazy dog"
    assert diagnostics[0].sliding_overlap is True
    assert diagnostics[0].rolling_growth is False


def test_cjk_sliding_overlap_via_character_overlap_not_whitespace_tokens():
    observations = [
        _observation("o1", "今日は天気が良い", 0.0, 2.0, language="ja"),
        _observation("o2", "天気が良いので散歩する", 1.5, 4.0, language="ja"),
    ]

    cues, diagnostics = reconstruct_cues_with_diagnostics(observations)

    assert len(cues) == 1
    assert cues[0].language_layers[0].text == "今日は天気が良いので散歩する"
    assert diagnostics[0].sliding_overlap is True


# -- Repetition / backtrack ----------------------------------------------------


def test_exact_duplicate_reading_is_collapsed_and_flagged_repetition():
    observations = [
        _observation("o1", "Hello world", 0.0, 2.0),
        _observation("o2", "Hello world", 2.1, 4.0),  # exact repeat, no new content
    ]

    cues, diagnostics = reconstruct_cues_with_diagnostics(observations)

    assert len(cues) == 1
    assert cues[0].language_layers[0].text == "Hello world"
    assert cues[0].language_layers[0].observation_ids == ("o1", "o2")  # provenance kept
    assert diagnostics[0].repetition_collapsed is True
    assert diagnostics[0].rolling_growth is False


def test_backtrack_where_next_text_is_a_pure_suffix_repeat_is_flagged_repetition():
    observations = [
        _observation("o1", "Hello world, how are you", 0.0, 2.0),
        _observation("o2", "how are you", 2.1, 4.0),  # repeats the tail, adds nothing new
    ]

    cues, diagnostics = reconstruct_cues_with_diagnostics(observations)

    assert len(cues) == 1
    assert cues[0].language_layers[0].text == "Hello world, how are you"
    assert diagnostics[0].repetition_collapsed is True


# -- Timing collision (overlap, no textual relation) ---------------------------


def test_overlapping_but_textually_unrelated_cues_are_kept_separate_and_flagged_collision():
    observations = [
        _observation("o1", "Speaker A says something long", 0.0, 5.0),
        _observation("o2", "Speaker B interjects briefly", 1.0, 3.0),
    ]

    cues, diagnostics = reconstruct_cues_with_diagnostics(observations)

    assert len(cues) == 2
    assert cues[0].language_layers[0].text == "Speaker A says something long"
    assert cues[1].language_layers[0].text == "Speaker B interjects briefly"
    assert diagnostics[1].timing_collision is True
    assert diagnostics[0].timing_collision is False  # only the later Cue carries the flag


# -- Segmentation ambiguity: a coincidental single-character match ------------


def test_a_single_coincidental_character_match_is_not_treated_as_real_continuation():
    # "...a lot" ends with "t"; "totally different..." starts with "t" --
    # a length-1 character match, purely coincidental, not real evidence
    # of a rolling continuation. The old M1 baseline (`overlap > 0`)
    # would have wrongly merged these into one garbled Cue.
    observations = [
        _observation("o1", "Thanks a lot", 0.0, 2.0),
        _observation("o2", "totally different topic", 1.5, 4.0),
    ]

    cues, diagnostics = reconstruct_cues_with_diagnostics(observations)

    assert len(cues) == 2
    assert cues[0].language_layers[0].text == "Thanks a lot"
    assert cues[1].language_layers[0].text == "totally different topic"
    assert diagnostics[1].segmentation_ambiguous is True
    assert diagnostics[1].rolling_growth is False
    assert diagnostics[1].sliding_overlap is False


# -- Temporal eligibility: text overlap alone must never merge ---------------


def test_far_distant_identical_captions_are_not_collapsed():
    # A real risk: two temporally UNRELATED captions that happen to
    # have identical text (e.g. "Thank you for watching" repeated at
    # the start and again minutes later) must stay two separate Cues.
    # Text identity is not evidence of a rolling continuation across an
    # arbitrary time gap.
    observations = [
        _observation("o1", "Thank you for watching", 0.0, 2.0),
        _observation("o2", "Thank you for watching", 120.0, 122.0),
    ]

    cues, _diagnostics = reconstruct_cues_with_diagnostics(observations)

    assert len(cues) == 2
    assert cues[0].language_layers[0].text == "Thank you for watching"
    assert cues[1].language_layers[0].text == "Thank you for watching"
    assert (cues[0].start_time, cues[0].end_time) == (0.0, 2.0)
    assert (cues[1].start_time, cues[1].end_time) == (120.0, 122.0)


def test_non_overlapping_adjacent_sentences_with_a_coincidental_boundary_match_are_not_merged():
    # Two ordinary, unrelated, non-overlapping sentences that happen to
    # share a real (2+ character) suffix/prefix at their boundary --
    # e.g. both mention "day" -- must not be merged just because the
    # text overlap check alone would have accepted it. There is no
    # temporal evidence of a rolling relationship at all.
    observations = [
        _observation("o1", "It was a bright cold day", 0.0, 2.0),
        _observation("o2", "day after day it rained", 2.5, 4.0),
    ]

    cues, _diagnostics = reconstruct_cues_with_diagnostics(observations)

    assert len(cues) == 2
    assert cues[0].language_layers[0].text == "It was a bright cold day"
    assert cues[1].language_layers[0].text == "day after day it rained"


def test_near_adjacent_duplicate_within_the_bounded_gap_still_collapses():
    # The one allowed exception: an EXACT duplicate reading (no new
    # content at all) within a small, fixed, fixture-justified gap is
    # still treated as a repeated/backtracking reading, not a real
    # temporal-overlap requirement -- this mirrors how repeated OCR-like
    # readings of the same caption can land in consecutive SRT entries
    # with a small gap rather than genuine time overlap.
    observations = [
        _observation("o1", "Thank you for watching", 0.0, 2.0),
        _observation("o2", "Thank you for watching", 2.3, 4.0),
    ]

    cues, diagnostics = reconstruct_cues_with_diagnostics(observations)

    assert len(cues) == 1
    assert cues[0].language_layers[0].text == "Thank you for watching"
    assert diagnostics[0].repetition_collapsed is True


# -- Irregular timing span: Cue end must cover ALL supporting evidence -------


def test_merged_cue_span_covers_the_latest_end_time_not_just_the_last_observation():
    # A run whose members' end_times are NOT monotonically increasing
    # with start_time (e.g. a long-duration first reading, then a
    # shorter-duration later reading nested inside it) must still span
    # every supporting Observation's real evidence -- not silently
    # truncate to whichever Observation happens to be last in the run.
    observations = [
        _observation("o1", "Hello", 0.0, 5.0),  # starts first, ends LATEST
        _observation("o2", "Hello world", 1.0, 3.0),  # starts later, ends EARLIER
    ]

    cues, _diagnostics = reconstruct_cues_with_diagnostics(observations)

    assert len(cues) == 1
    assert cues[0].start_time == 0.0
    assert cues[0].end_time == 5.0  # the latest real end_time among supporting evidence
    assert cues[0].language_layers[0].text == "Hello world"


# -- CJK: a real single-character whole-caption growth vs. a coincidence -----


def test_cjk_single_character_whole_prefix_growth_is_real_rolling_growth():
    # A one-character caption that grows into a longer one, retaining
    # the ENTIRE original character as its own prefix, is genuine
    # rolling growth even though the overlap length (1) is below the
    # general coincidence-guard floor -- the floor exists to guard
    # against a coincidental PARTIAL match on a much longer text, not
    # to reject a real, fully-retained short caption.
    observations = [
        _observation("o1", "你", 0.0, 2.0, language="zh"),
        _observation("o2", "你好，世界", 1.0, 4.0, language="zh"),
    ]

    cues, diagnostics = reconstruct_cues_with_diagnostics(observations)

    assert len(cues) == 1
    assert cues[0].language_layers[0].text == "你好，世界"
    assert diagnostics[0].rolling_growth is True
    assert diagnostics[0].segmentation_ambiguous is False


def test_cjk_single_character_coincidental_boundary_match_is_not_growth():
    # A longer CJK caption whose LAST character happens to match the
    # FIRST character of a temporally-overlapping but textually
    # UNRELATED next caption -- a coincidence, not evidence of growth
    # (the accumulated text is NOT fully retained as a prefix; only its
    # last character coincidentally matches). Must be treated exactly
    # like the analogous English single-character coincidence case, not
    # given CJK-specific leniency.
    observations = [
        _observation("o1", "今日は天気が良", 0.0, 2.0, language="ja"),
        _observation("o2", "良かったね、また明日", 1.5, 4.0, language="ja"),
    ]

    cues, diagnostics = reconstruct_cues_with_diagnostics(observations)

    assert len(cues) == 2
    assert cues[0].language_layers[0].text == "今日は天気が良"
    assert cues[1].language_layers[0].text == "良かったね、また明日"
    assert diagnostics[1].segmentation_ambiguous is True
    assert diagnostics[1].rolling_growth is False


# -- Out-of-order source cues: diagnose, don't silently discard ---------------


def test_out_of_order_source_cues_are_still_correctly_timed_and_flagged():
    # Observations are handed in out of chronological order (as a
    # malformed/hand-edited source file might produce) -- reconstruction
    # must still time everything correctly (sorting for processing is
    # fine) AND must not silently hide the fact that the source was out
    # of order: the resulting Cue(s) touching the reordered observation
    # carry source_order_issue=True.
    observations = [
        _observation("o2", "Second complete sentence.", 2.1, 4.0),
        _observation("o1", "First complete sentence.", 0.0, 2.0),
    ]

    cues, diagnostics = reconstruct_cues_with_diagnostics(observations)

    assert [cue.language_layers[0].text for cue in cues] == [
        "First complete sentence.",
        "Second complete sentence.",
    ]
    assert [(cue.start_time, cue.end_time) for cue in cues] == [(0.0, 2.0), (2.1, 4.0)]
    assert any(d.source_order_issue for d in diagnostics)


def test_source_cues_already_in_chronological_order_have_no_order_issue():
    observations = [
        _observation("o1", "First complete sentence.", 0.0, 2.0),
        _observation("o2", "Second complete sentence.", 2.1, 4.0),
    ]

    _cues, diagnostics = reconstruct_cues_with_diagnostics(observations)

    assert all(not d.source_order_issue for d in diagnostics)


# -- reconstruct_cues() stays a thin, diagnostics-discarding wrapper ----------


def test_reconstruct_cues_matches_the_cue_half_of_reconstruct_cues_with_diagnostics():
    observations = [
        _observation("o1", "Hello", 0.0, 2.0),
        _observation("o2", "Hello world", 1.0, 4.0),
    ]

    cues_only = reconstruct_cues(observations)
    cues_with_diagnostics, _diagnostics = reconstruct_cues_with_diagnostics(observations)

    assert cues_only == cues_with_diagnostics
