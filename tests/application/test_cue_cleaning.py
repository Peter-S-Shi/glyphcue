from __future__ import annotations

from glyphcue.application import cue_cleaning
from glyphcue.application.cue_cleaning import (
    _reconstruct_cue,
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


def _bilingual_cue(id_, start, end, en_text="hello", zh_text="你好", review_state=ReviewState.PENDING,
                    en_observation_ids=(), zh_observation_ids=()):
    return Cue(
        id=id_,
        start_time=start,
        end_time=end,
        language_layers=(
            LanguageLayer(language="en", text=en_text, observation_ids=en_observation_ids),
            LanguageLayer(language="zh", text=zh_text, observation_ids=zh_observation_ids),
        ),
        review_state=review_state,
    )


def _assert_valid_timing(cues):
    for cue in cues:
        assert cue.start_time >= 0
        assert cue.end_time > cue.start_time


def test_is_cleaner_eligible_cue_requires_pending_regardless_of_layer_count():
    assert is_cleaner_eligible_cue(_cue("c1", 0.0, 1.0, review_state=ReviewState.PENDING))
    assert is_cleaner_eligible_cue(_bilingual_cue("c1", 0.0, 1.0, review_state=ReviewState.PENDING))
    assert not is_cleaner_eligible_cue(_cue("c1", 0.0, 1.0, review_state=ReviewState.APPROVED))
    assert not is_cleaner_eligible_cue(_cue("c1", 0.0, 1.0, review_state=ReviewState.REJECTED))
    assert not is_cleaner_eligible_cue(_cue("c1", 0.0, 1.0, review_state=ReviewState.NEEDS_REVIEW))


def test_no_eligible_cues_is_a_safe_no_op():
    cues = [
        _cue("c1", 0.0, 1.0, review_state=ReviewState.APPROVED),
        _bilingual_cue("c2", 1.0, 2.0, review_state=ReviewState.NEEDS_REVIEW),
    ]

    result = clean_eligible_cues_for_source(cues)

    assert {c.id for c in result} == {"c1", "c2"}
    assert result[0].review_state == ReviewState.APPROVED
    _assert_valid_timing(result)


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
    _assert_valid_timing(result)


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
    _assert_valid_timing(result)


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
    _assert_valid_timing(result)


def test_preserve_complementary_evidence_cluster_maps_to_needs_review_even_when_unchanged(monkeypatch):
    """Regression test for a real contract bug: a
    `preserve_complementary_evidence_cluster` member is very often an
    UNCHANGED single-origin observed Cue (the whole point of the
    evidence cover is picking already-complete, already-correct
    observations) -- the frozen Cleaner's own real output shape for
    this action gives each cover member `source_indices=(its own single
    origin index,)`, exactly like an ordinary untouched passthrough.
    Earlier this made the adapter's is-unchanged-passthrough shortcut
    return the original PENDING Cue before ever consulting the
    needs-review mapping. The fake report below mirrors that real shape
    (NOT `source_indices=(1, 2)` for both members, which would mask the
    bug) -- deterministically exercising the adapter's own mapping
    logic without depending on reverse-engineering the frozen
    algorithm's exact clustering thresholds (already independently
    validated by its own frozen-corpus freeze report: 9 real
    complementary-evidence clusters found in Sample A-H)."""

    def fake_clean_cues(frozen_cues):
        cleaned = [
            cue_cleaning.cleaner.Cue(
                index=1,
                start=frozen_cues[0].start,
                end=frozen_cues[0].end,
                text=frozen_cues[0].text,
                source_indices=(1,),
                selected_origin_index=1,
            ),
            cue_cleaning.cleaner.Cue(
                index=2,
                start=frozen_cues[1].start,
                end=frozen_cues[1].end,
                text=frozen_cues[1].text,
                source_indices=(2,),
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
    # Same id/provenance preserved -- only the review state flips.
    assert {c.id for c in result} == {"c1", "c2"}
    by_id = {c.id: c for c in result}
    assert by_id["c1"].language_layers[0].text == "...life of"
    assert by_id["c2"].language_layers[0].text == "abundance."
    _assert_valid_timing(result)


def test_preserve_complementary_evidence_cluster_does_not_reflag_already_needs_review(monkeypatch):
    """A protected (already NEEDS_REVIEW) Cue is never handed to the
    Cleaner at all (see `is_cleaner_eligible_cue`), so this only matters
    for the eligible/PENDING side -- but confirms the flip logic doesn't
    error when a Cue is already at NEEDS_REVIEW going in isn't possible
    here; this instead confirms it doesn't double-touch an unrelated
    ordinary PENDING passthrough result in the same batch."""

    def fake_clean_cues(frozen_cues):
        cleaned = [
            cue_cleaning.cleaner.Cue(
                index=1,
                start=frozen_cues[0].start,
                end=frozen_cues[0].end,
                text=frozen_cues[0].text,
                source_indices=(1,),
                selected_origin_index=1,
            ),
            cue_cleaning.cleaner.Cue(
                index=2,
                start=frozen_cues[1].start,
                end=frozen_cues[1].end,
                text=frozen_cues[1].text,
                source_indices=(2,),
                selected_origin_index=2,
            ),
        ]
        report = {"actions": []}
        return cleaned, report

    monkeypatch.setattr(cue_cleaning.cleaner, "clean_cues", fake_clean_cues)

    cues = [
        _cue("c1", 0.0, 1.0, text="one"),
        _cue("c2", 1.0, 2.0, text="two"),
    ]

    result = clean_eligible_cues_for_source(cues)

    assert {c.id: c.review_state for c in result} == {
        "c1": ReviewState.PENDING,
        "c2": ReviewState.PENDING,
    }


# --- Bilingual / multi-language-layer reconstruction -----------------


def test_bilingual_cue_is_eligible_and_passes_through_unchanged_when_unique():
    cue = _bilingual_cue("c1", 0.0, 1.0, en_text="a unique line", zh_text="一句独特的话")

    result = clean_eligible_cues_for_source([cue])

    assert len(result) == 1
    assert result[0].id == "c1"
    assert result[0].review_state == ReviewState.PENDING
    layers = {layer.language: layer.text for layer in result[0].language_layers}
    assert layers == {"en": "a unique line", "zh": "一句独特的话"}
    _assert_valid_timing(result)


def test_bilingual_duplicate_adjacent_cues_merge_and_split_back_to_correct_layers():
    """Two adjacent bilingual Cues with identical text in both layers
    should merge into one -- and each language layer's text must be
    correctly attributed back to its own layer, never mixed."""
    cues = [
        _bilingual_cue(
            "c1", 0.0, 1.0, en_text="hello world", zh_text="你好世界",
            en_observation_ids=("en1",), zh_observation_ids=("zh1",),
        ),
        _bilingual_cue(
            "c2", 1.0, 2.0, en_text="hello world", zh_text="你好世界",
            en_observation_ids=("en2",), zh_observation_ids=("zh2",),
        ),
    ]

    result = clean_eligible_cues_for_source(cues)

    assert len(result) == 1
    merged = result[0]
    assert merged.start_time == 0.0
    assert merged.end_time == 2.0
    assert merged.review_state == ReviewState.PENDING
    layers = {layer.language: layer for layer in merged.language_layers}
    assert layers["en"].text == "hello world"
    assert layers["zh"].text == "你好世界"
    # Evidence unioned per language layer, never cross-attributed.
    assert set(layers["en"].observation_ids) == {"en1", "en2"}
    assert set(layers["zh"].observation_ids) == {"zh1", "zh2"}
    _assert_valid_timing(result)


def test_bilingual_cue_with_distinct_content_stays_separate():
    cues = [
        _bilingual_cue("c1", 0.0, 1.0, en_text="first line", zh_text="第一行"),
        _bilingual_cue("c2", 5.0, 6.0, en_text="second line", zh_text="第二行"),
    ]

    result = clean_eligible_cues_for_source(cues)

    assert {c.id for c in result} == {"c1", "c2"}
    _assert_valid_timing(result)


def test_reconstruct_multilayer_cue_returns_none_when_output_line_is_not_a_verbatim_donor_line():
    """Direct unit test of the safety net: if a cleaned output line
    cannot be matched, verbatim and in order, against its donor's own
    known lines (e.g. the rare content-modifying
    strip_persistent_overlay_edges post-pass), attribution must refuse
    to guess rather than silently mis-route a line to the wrong
    language layer."""
    donor = _bilingual_cue("donor", 0.0, 1.0, en_text="hello world", zh_text="你好")
    donor_attribution = cue_cleaning._joined_lines_with_layer_index(donor)

    frozen_cue = cue_cleaning.cleaner.Cue(
        index=1,
        start=0.0,
        end=1.0,
        text="hello there",  # modified, not a verbatim donor line
        source_indices=(1,),
        selected_origin_index=1,
    )

    result = _reconstruct_cue(
        frozen_cue, [donor], donor, donor_attribution, needs_review=False
    )

    assert result is None


def test_clean_eligible_cues_falls_back_to_untouched_when_attribution_is_unsafe(monkeypatch):
    """End-to-end: when the Cleaner's real output can't be safely
    attributed back to language layers, the adapter must leave every
    contributing Cue exactly as it was -- never guess, never lose or
    mis-attribute evidence."""

    def fake_clean_cues(frozen_cues):
        cleaned = [
            cue_cleaning.cleaner.Cue(
                index=1,
                start=frozen_cues[0].start,
                end=frozen_cues[0].end,
                text="a line that was never actually observed",
                source_indices=(1,),
                selected_origin_index=1,
            ),
        ]
        return cleaned, {"actions": []}

    monkeypatch.setattr(cue_cleaning.cleaner, "clean_cues", fake_clean_cues)

    original = _bilingual_cue("c1", 0.0, 1.0, en_text="hello world", zh_text="你好")

    result = clean_eligible_cues_for_source([original])

    assert len(result) == 1
    assert result[0] is original


def test_bilingual_layer_fully_pruned_is_flagged_needs_review(monkeypatch):
    """If cleaning would leave one language layer completely empty
    while the Cue itself still has content, that is a meaningfully
    different outcome from routine pruning and must be surfaced for
    human review rather than silently accepted."""

    def fake_clean_cues(frozen_cues):
        # Simulate: only the English line survived a real cleaning pass
        # (e.g. prune_transient_lines dropped the Chinese line as
        # unsupported). This is a real, in-order subsequence of the
        # donor's own lines -- a legitimate frozen-algorithm outcome.
        cleaned = [
            cue_cleaning.cleaner.Cue(
                index=1,
                start=frozen_cues[0].start,
                end=frozen_cues[0].end,
                text="hello world",
                source_indices=(1,),
                selected_origin_index=1,
            ),
        ]
        return cleaned, {"actions": []}

    monkeypatch.setattr(cue_cleaning.cleaner, "clean_cues", fake_clean_cues)

    original = _bilingual_cue("c1", 0.0, 1.0, en_text="hello world", zh_text="你好")

    result = clean_eligible_cues_for_source([original])

    assert len(result) == 1
    cleaned_cue = result[0]
    assert cleaned_cue.review_state == ReviewState.NEEDS_REVIEW
    layers = {layer.language: layer.text for layer in cleaned_cue.language_layers}
    assert layers["en"] == "hello world"
    assert layers["zh"] == ""


# --- Corrective round B --------------------------------------------


def test_single_language_content_modifying_result_is_accepted_not_reverted(monkeypatch):
    """A single-language Cue has no cross-layer attribution question at
    all: the frozen Cleaner's returned text must be accepted directly,
    even when it differs from every original line verbatim (e.g. the
    real `strip_persistent_overlay_edges` post-pass, which strips a
    persistent overlay phrase as a prefix/suffix of a longer line --
    genuinely modifying that line's text, not merely keeping or
    dropping it whole). Previously this was indistinguishable from an
    unsafe multi-language attribution and the original Cue was reverted
    instead of accepting the real, intended Cleaner result."""

    def fake_clean_cues(frozen_cues):
        cleaned = [
            cue_cleaning.cleaner.Cue(
                index=1,
                start=frozen_cues[0].start,
                end=frozen_cues[0].end,
                text="a real subtitle line",  # edge-stripped, not a verbatim donor line
                source_indices=(1,),
                selected_origin_index=1,
            ),
        ]
        return cleaned, {"actions": []}

    monkeypatch.setattr(cue_cleaning.cleaner, "clean_cues", fake_clean_cues)

    original = _cue(
        "c1", 0.0, 1.0,
        text="Speaker: Mel Robbins a real subtitle line",
        observation_ids=("o1",),
    )

    result = clean_eligible_cues_for_source([original])

    assert len(result) == 1
    cleaned_cue = result[0]
    # Accepted directly -- not reverted to the original overlay-laden text.
    assert cleaned_cue.language_layers[0].text == "a real subtitle line"
    assert cleaned_cue.review_state == ReviewState.PENDING
    assert set(cleaned_cue.language_layers[0].observation_ids) == {"o1"}
    _assert_valid_timing(result)


def test_different_language_signatures_are_never_cleaned_together():
    """Cues from an earlier single-language OCR range must never be
    merged with, or have their evidence cross-unioned with, Cues from a
    later run under a different Track Group language configuration."""
    english_only = _cue("en1", 0.0, 1.0, language="en", text="hello world", observation_ids=("oe1",))
    chinese_only = _cue("zh1", 1.0, 2.0, language="zh", text="hello world", observation_ids=("oz1",))

    result = clean_eligible_cues_for_source([english_only, chinese_only])

    # Identical compacted text would ordinarily merge two same-signature
    # Cues (see test_duplicate_adjacent_eligible_cues_are_merged_and_stay_pending)
    # -- but different signatures must keep them completely separate.
    assert {c.id for c in result} == {"en1", "zh1"}
    by_id = {c.id: c for c in result}
    assert by_id["en1"].language_layers[0].observation_ids == ("oe1",)
    assert by_id["zh1"].language_layers[0].observation_ids == ("oz1",)


def test_reversed_bilingual_language_order_is_a_distinct_signature():
    """`("en", "zh")` and `("zh", "en")` are different signatures even
    though they share the same two languages -- never merged."""
    en_then_zh = Cue(
        id="c1", start_time=0.0, end_time=1.0,
        language_layers=(
            LanguageLayer(language="en", text="hello"),
            LanguageLayer(language="zh", text="你好"),
        ),
        review_state=ReviewState.PENDING,
    )
    zh_then_en = Cue(
        id="c2", start_time=1.0, end_time=2.0,
        language_layers=(
            LanguageLayer(language="zh", text="你好"),
            LanguageLayer(language="en", text="hello"),
        ),
        review_state=ReviewState.PENDING,
    )

    result = clean_eligible_cues_for_source([en_then_zh, zh_then_en])

    assert {c.id for c in result} == {"c1", "c2"}
    by_id = {c.id: c for c in result}
    assert [layer.language for layer in by_id["c1"].language_layers] == ["en", "zh"]
    assert [layer.language for layer in by_id["c2"].language_layers] == ["zh", "en"]


def test_ambiguous_shared_line_between_layers_fails_closed(monkeypatch):
    """If identical text appears in two of a donor's own language
    layers (e.g. a shared code/number), a surviving output line with
    that exact text cannot be uniquely attributed to either layer from
    content+order alone. The adapter must refuse to guess and leave the
    affected result untouched, rather than silently routing it to
    whichever layer the forward scan happens to reach first."""

    def fake_clean_cues(frozen_cues):
        # The donor's own joined text is "007\nhello\n007\n你好" (see
        # donor construction below): "007" appears in both the en and
        # zh layers. Simulate a real merge/prune pass surviving down to
        # just the shared, ambiguous line.
        cleaned = [
            cue_cleaning.cleaner.Cue(
                index=1,
                start=frozen_cues[0].start,
                end=frozen_cues[0].end,
                text="007",
                source_indices=(1,),
                selected_origin_index=1,
            ),
        ]
        return cleaned, {"actions": []}

    monkeypatch.setattr(cue_cleaning.cleaner, "clean_cues", fake_clean_cues)

    donor = _bilingual_cue("c1", 0.0, 1.0, en_text="007\nhello", zh_text="007\n你好")

    result = clean_eligible_cues_for_source([donor])

    # Unsafe to attribute -- the Cue is left completely untouched.
    assert len(result) == 1
    assert result[0] is donor


def test_unsafe_attribution_fallback_still_flags_complementary_evidence_as_needs_review(monkeypatch):
    """The frozen `preserve_complementary_evidence_cluster` contract must
    hold even when the text/layer-level reconstruction itself has to be
    abandoned as unsafe: the donor Cue that action selected must still
    surface as NEEDS_REVIEW with its original id/text/timing/provenance,
    never silently revert to PENDING."""

    def fake_clean_cues(frozen_cues):
        cleaned = [
            cue_cleaning.cleaner.Cue(
                index=1,
                start=frozen_cues[0].start,
                end=frozen_cues[0].end,
                text="a line that was never actually observed",
                source_indices=(1,),
                selected_origin_index=1,
            ),
        ]
        report = {
            "actions": [
                {
                    "action": "preserve_complementary_evidence_cluster",
                    "source_cues": [1],
                    "selected_source_cues": [1],
                }
            ]
        }
        return cleaned, report

    monkeypatch.setattr(cue_cleaning.cleaner, "clean_cues", fake_clean_cues)

    original = _bilingual_cue("c1", 0.0, 1.0, en_text="hello world", zh_text="你好", en_observation_ids=("o1",))

    result = clean_eligible_cues_for_source([original])

    assert len(result) == 1
    flagged = result[0]
    assert flagged.id == "c1"
    assert flagged.review_state == ReviewState.NEEDS_REVIEW
    # Original text/timing/provenance untouched -- only review_state changed.
    layers = {layer.language: layer.text for layer in flagged.language_layers}
    assert layers == {"en": "hello world", "zh": "你好"}
    assert flagged.start_time == 0.0
    assert flagged.end_time == 1.0
    en_layer = next(l for l in flagged.language_layers if l.language == "en")
    assert en_layer.observation_ids == ("o1",)


def test_noise_split_persistent_caption_does_not_survive_as_duplicate_text():
    """Human QA Case A (release-blocking): a real, persistent caption
    observed across several consecutive near-duplicate OCR frames can be
    interrupted by a single garbled frame whose text is not a pure
    substring of the caption (so `absorb_redundant_micro_fragments`
    cannot safely fold it into a neighbor). The frozen Cleaner's
    adjacency-based clustering (`clean_one_pass`) then splits the burst
    into two separate clusters that each *independently* reduce to the
    exact same caption text -- two domain Cues that are text-identical
    representations of one single real observed moment, with the noisy
    frame surviving as its own tiny Cue in between. A human reviewer
    sees this as the same line "duplicated". This is the minimized,
    deterministic repro of that defect (3 input Cues is already
    sufficient)."""
    caption = "我直接从三个最具体的问题拆解"
    noisy = caption[: len(caption) // 2] + "口"
    cues = [
        _cue("c1", 0.00, 0.09, text=caption, language="zh", observation_ids=("o1",)),
        _cue("c2", 0.09, 0.18, text=noisy, language="zh", observation_ids=("o2",)),
        _cue("c3", 0.18, 0.27, text=caption, language="zh", observation_ids=("o3",)),
    ]

    result = clean_eligible_cues_for_source(cues)

    texts = [layer.text for cue in result for layer in cue.language_layers]
    assert texts.count(caption) <= 1, (
        f"the persistent caption survived as more than one domain Cue: {result}"
    )
    _assert_valid_timing(result)

    # Second click: idempotent, no further change.
    result2 = clean_eligible_cues_for_source(result)
    texts2 = [layer.text for cue in result2 for layer in cue.language_layers]
    assert texts2.count(caption) <= 1
    assert len(result2) == len(result)

    merged = next(
        cue for cue in result
        if any(layer.text == caption for layer in cue.language_layers)
    )
    assert merged.review_state == ReviewState.NEEDS_REVIEW
    assert merged.start_time == 0.00
    assert merged.end_time == 0.27
    merged_layer = merged.language_layers[0]
    assert merged_layer.observation_ids == ("o1", "o3")

    # The genuinely distinct garbled frame is untouched, still PENDING,
    # still its own Cue -- the fix must not remove real (non-duplicate)
    # evidence, only collapse the exact-text-duplicate split.
    noisy_cue = next(
        cue for cue in result
        if any(layer.text == noisy for layer in cue.language_layers)
    )
    assert noisy_cue.review_state == ReviewState.PENDING
    assert noisy_cue.id == "c2"


def test_split_duplicate_collapse_never_merges_distant_unrelated_repeats():
    """Two Cues sharing exact text but far apart in time (further than
    the frozen Cleaner's own max_cluster_span_seconds default of 8.0s)
    are legitimately independent real repeats of the same dialogue, not
    a single observation split apart by clustering noise -- e.g. the
    same short phrase said twice, minutes apart. The split-duplicate
    safety net must never merge these; distant identical text is not
    evidence of a Cleaner-side split artifact."""
    cues = [
        _cue("c1", 0.0, 1.0, text="谢谢观看", observation_ids=("o1",)),
        _cue("c2", 120.0, 121.0, text="谢谢观看", observation_ids=("o2",)),
    ]

    result = clean_eligible_cues_for_source(cues)

    assert {c.id for c in result} == {"c1", "c2"}
    assert all(c.review_state == ReviewState.PENDING for c in result)
