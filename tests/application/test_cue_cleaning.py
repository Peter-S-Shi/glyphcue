from __future__ import annotations

from glyphcue.application import cue_cleaning
from glyphcue.application.cue_cleaning import (
    clean_eligible_cues_for_source,
    is_cleaner_eligible_cue,
)
from glyphcue.domain.cue import Cue
from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.domain.review_state import ReviewState


def _cue(id_, start, end, text="hello", language="en", review_state=ReviewState.PENDING, observation_ids=()):
    return Cue(
        id=id_,
        start_time=start,
        end_time=end,
        language_layers=(LanguageLayer(language=language, text=text, observation_ids=observation_ids),),
        review_state=review_state,
    )


def _multilang_cue(id_, start, end, review_state=ReviewState.PENDING):
    return Cue(
        id=id_,
        start_time=start,
        end_time=end,
        language_layers=(
            LanguageLayer(language="en", text="hello"),
            LanguageLayer(language="zh", text="你好"),
        ),
        review_state=review_state,
    )


def test_is_cleaner_eligible_cue_requires_pending_and_single_language_layer():
    assert is_cleaner_eligible_cue(_cue("c1", 0.0, 1.0, review_state=ReviewState.PENDING))
    assert not is_cleaner_eligible_cue(_cue("c1", 0.0, 1.0, review_state=ReviewState.APPROVED))
    assert not is_cleaner_eligible_cue(_cue("c1", 0.0, 1.0, review_state=ReviewState.REJECTED))
    assert not is_cleaner_eligible_cue(_cue("c1", 0.0, 1.0, review_state=ReviewState.NEEDS_REVIEW))
    assert not is_cleaner_eligible_cue(_multilang_cue("c1", 0.0, 1.0))


def test_no_eligible_cues_is_a_safe_no_op():
    cues = [
        _cue("c1", 0.0, 1.0, review_state=ReviewState.APPROVED),
        _multilang_cue("c2", 1.0, 2.0),
    ]

    result = clean_eligible_cues_for_source(cues)

    assert {c.id for c in result} == {"c1", "c2"}
    assert result[0].review_state == ReviewState.APPROVED


def test_empty_cue_list_is_a_safe_no_op():
    assert clean_eligible_cues_for_source([]) == []


def test_unchanged_eligible_cue_keeps_its_own_id_and_state():
    """A Cue the Cleaner leaves semantically untouched (no duplicate/
    adjacent evidence to merge) must not appear to change identity --
    same id, same PENDING state -- so an unaffected Cue never looks
    different across a Clean Cues click."""
    cue = _cue("c1", 0.0, 1.0, text="a completely unique caption")

    result = clean_eligible_cues_for_source([cue])

    assert len(result) == 1
    assert result[0].id == "c1"
    assert result[0].review_state == ReviewState.PENDING
    assert result[0].language_layers[0].text == "a completely unique caption"


def test_duplicate_adjacent_eligible_cues_are_merged_and_stay_pending():
    cues = [
        _cue("c1", 0.0, 1.0, text="hello world", observation_ids=("o1",)),
        _cue("c2", 1.0, 2.0, text="hello world", observation_ids=("o2",)),
    ]

    result = clean_eligible_cues_for_source(cues)

    assert len(result) == 1
    merged = result[0]
    assert merged.start_time == 0.0
    assert merged.end_time == 2.0
    assert merged.language_layers[0].text == "hello world"
    assert merged.review_state == ReviewState.PENDING
    # Evidence from both contributing Cues is preserved, not dropped.
    assert set(merged.language_layers[0].observation_ids) == {"o1", "o2"}


def test_protected_cues_survive_completely_unchanged():
    approved = _cue("approved", 0.0, 1.0, text="hello world", review_state=ReviewState.APPROVED)
    rejected = _cue("rejected", 1.0, 2.0, text="hello world", review_state=ReviewState.REJECTED)
    needs_review = _cue("needs_review", 2.0, 3.0, text="hello world", review_state=ReviewState.NEEDS_REVIEW)
    eligible = _cue("eligible", 3.0, 4.0, text="a distinct caption")

    result = clean_eligible_cues_for_source([approved, rejected, needs_review, eligible])

    by_id = {c.id: c for c in result}
    assert by_id["approved"] is approved
    assert by_id["rejected"] is rejected
    assert by_id["needs_review"] is needs_review
    assert by_id["eligible"].review_state == ReviewState.PENDING


def test_multilanguage_cues_pass_through_untouched_even_when_duplicated():
    """Documented scope boundary: multi-language-layer Cues are never
    cleaner-eligible (see `is_cleaner_eligible_cue`), even if a naive
    single-language reading would treat them as duplicates."""
    first = _multilang_cue("m1", 0.0, 1.0)
    second = _multilang_cue("m2", 1.0, 2.0)

    result = clean_eligible_cues_for_source([first, second])

    assert {c.id for c in result} == {"m1", "m2"}
    assert all(len(c.language_layers) == 2 for c in result)


def test_cleaning_twice_is_idempotent():
    cues = [
        _cue("c1", 0.0, 1.0, text="hello world", observation_ids=("o1",)),
        _cue("c2", 1.0, 2.0, text="hello world", observation_ids=("o2",)),
        _cue("c3", 2.0, 3.0, text="a distinct caption", observation_ids=("o3",)),
    ]

    once = clean_eligible_cues_for_source(cues)
    twice = clean_eligible_cues_for_source(once)

    assert len(once) == len(twice)
    for a, b in zip(
        sorted(once, key=lambda c: c.start_time),
        sorted(twice, key=lambda c: c.start_time),
    ):
        assert a.id == b.id
        assert a.start_time == b.start_time
        assert a.end_time == b.end_time
        assert a.language_layers[0].text == b.language_layers[0].text
        assert a.review_state == b.review_state


def test_result_is_sorted_chronologically():
    cues = [
        _cue("late", 5.0, 6.0, text="one"),
        _cue("early", 0.0, 1.0, text="two"),
        _cue("mid", 2.0, 3.0, text="three", review_state=ReviewState.APPROVED),
    ]

    result = clean_eligible_cues_for_source(cues)

    assert [c.id for c in result] == ["early", "mid", "late"]
    for a, b in zip(result, result[1:]):
        assert a.start_time <= b.start_time


def test_preserve_complementary_evidence_cluster_maps_to_needs_review(monkeypatch):
    """Deterministically exercises the adapter's own mapping logic for the
    Cleaner's conservative complementary-evidence-cover fallback, without
    depending on reverse-engineering the frozen algorithm's exact
    clustering thresholds (already independently validated by its own
    frozen-corpus freeze report: 9 real complementary-evidence clusters
    found in Sample A-H)."""

    def fake_clean_cues(frozen_cues):
        # Simulate: two eligible Cues (origin indices 1 and 2) were found
        # to hold complementary recurring evidence with no single Cue
        # covering both -- the Cleaner keeps both, unmodified, flagged
        # for human review, exactly like `choose_evidence_cover` would.
        cleaned = [
            cue_cleaning.cleaner.Cue(
                index=1,
                start=frozen_cues[0].start,
                end=frozen_cues[0].end,
                text=frozen_cues[0].text,
                source_indices=(1, 2),
                selected_origin_index=1,
            ),
            cue_cleaning.cleaner.Cue(
                index=2,
                start=frozen_cues[1].start,
                end=frozen_cues[1].end,
                text=frozen_cues[1].text,
                source_indices=(1, 2),
                selected_origin_index=2,
            ),
        ]
        report = {
            "actions": [
                {
                    "action": "preserve_complementary_evidence_cluster",
                    "source_cues": [1, 2],
                    "selected_source_cues": [1, 2],
                }
            ]
        }
        return cleaned, report

    monkeypatch.setattr(cue_cleaning.cleaner, "clean_cues", fake_clean_cues)

    cues = [
        _cue("c1", 0.0, 1.0, text="...life of", observation_ids=("o1",)),
        _cue("c2", 1.0, 2.0, text="abundance.", observation_ids=("o2",)),
    ]

    result = clean_eligible_cues_for_source(cues)

    assert len(result) == 2
    assert all(c.review_state == ReviewState.NEEDS_REVIEW for c in result)
    texts = {c.language_layers[0].text for c in result}
    assert texts == {"...life of", "abundance."}
