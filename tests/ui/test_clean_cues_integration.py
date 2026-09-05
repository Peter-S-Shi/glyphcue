from pathlib import Path

from glyphcue.domain.cue import Cue
from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.domain.review_state import ReviewState
from glyphcue.persistence.database import connect
from glyphcue.persistence.repository import CueRepository
from glyphcue.persistence.track_group_repository import TrackGroupRepository
from glyphcue.ui.path_a_media_pane import PathAMediaPane


def _make_cue(id_, start, end, state=ReviewState.PENDING, text="test", observation_ids=()):
    layer = LanguageLayer(language="en", text=text, observation_ids=observation_ids)
    return Cue(id=id_, start_time=start, end_time=end, language_layers=(layer,), review_state=state)


def _make_multilang_cue(id_, start, end, state=ReviewState.PENDING):
    layers = (
        LanguageLayer(language="en", text="hello"),
        LanguageLayer(language="zh", text="你好"),
    )
    return Cue(id=id_, start_time=start, end_time=end, language_layers=layers, review_state=state)


def _make_pane(tmp_path, source_id="video_a", cues=()):
    db_path = tmp_path / "test.sqlite3"
    conn = connect(db_path)
    cue_repo = CueRepository(conn)
    tg_repo = TrackGroupRepository(conn)
    if cues:
        cue_repo.save_cues_for_source(source_id, list(cues))

    pane = PathAMediaPane(tg_repo, db_path=db_path, available_languages=["en"])
    pane._source_id = source_id
    pane._video_path = Path(f"{source_id}.mp4")
    pane.qa.set_cues_and_priorities(list(cues), {}, {})
    pane._update_clean_cues_button_enabled()
    return pane, cue_repo


def test_clean_cues_button_disabled_with_no_current_video(qapp_guard, tmp_path):
    pane, _ = _make_pane(tmp_path, cues=[])
    pane._source_id = None
    pane._update_clean_cues_button_enabled()

    assert not pane.clean_cues_button.isEnabled()

    # Safe no-op even if clicked directly.
    pane._on_clean_cues_clicked()
    assert pane.qa.cues == []


def test_clean_cues_button_disabled_when_no_eligible_cues(qapp_guard, tmp_path):
    cues = [
        _make_cue("c1", 0.0, 1.0, state=ReviewState.APPROVED),
        _make_cue("c2", 1.0, 2.0, state=ReviewState.REJECTED),
    ]
    pane, cue_repo = _make_pane(tmp_path, cues=cues)

    assert not pane.clean_cues_button.isEnabled()

    pane._on_clean_cues_clicked()

    # Safe no-op: nothing changed.
    assert {c.id for c in pane.qa.cues} == {"c1", "c2"}
    assert {c.id for c in cue_repo.list_for_source("video_a")} == {"c1", "c2"}


def test_clean_cues_button_enabled_when_eligible_cues_exist(qapp_guard, tmp_path):
    cues = [_make_cue("c1", 0.0, 1.0)]
    pane, _ = _make_pane(tmp_path, cues=cues)

    assert pane.clean_cues_button.isEnabled()


def test_clean_cues_merges_duplicate_and_updates_workspace_and_persistence(qapp_guard, tmp_path):
    cues = [
        _make_cue("c1", 0.0, 1.0, text="hello world", observation_ids=("o1",)),
        _make_cue("c2", 1.0, 2.0, text="hello world", observation_ids=("o2",)),
    ]
    pane, cue_repo = _make_pane(tmp_path, cues=cues)

    pane._on_clean_cues_clicked()

    assert len(pane.qa.cues) == 1
    merged = pane.qa.cues[0]
    assert merged.start_time == 0.0
    assert merged.end_time == 2.0
    assert merged.language_layers[0].text == "hello world"
    assert merged.review_state == ReviewState.PENDING

    # Persistence reflects the same result (source-of-truth check).
    persisted = cue_repo.list_for_source("video_a")
    assert len(persisted) == 1
    assert persisted[0].language_layers[0].text == "hello world"


def test_clean_cues_only_touches_current_video_source(qapp_guard, tmp_path):
    db_path = tmp_path / "test.sqlite3"
    conn = connect(db_path)
    cue_repo = CueRepository(conn)
    tg_repo = TrackGroupRepository(conn)

    source_a = "video_a"
    source_b = "video_b"
    cues_a = [
        _make_cue("ca1", 0.0, 1.0, text="dup"),
        _make_cue("ca2", 1.0, 2.0, text="dup"),
    ]
    cues_b = [
        _make_cue("cb1", 0.0, 1.0, text="dup"),
        _make_cue("cb2", 1.0, 2.0, text="dup"),
    ]
    cue_repo.save_cues_for_source(source_a, cues_a)
    cue_repo.save_cues_for_source(source_b, cues_b)

    pane = PathAMediaPane(tg_repo, db_path=db_path, available_languages=["en"])
    pane._source_id = source_a
    pane._video_path = Path("video_a.mp4")
    pane.qa.set_cues_and_priorities(cues_a, {}, {})
    pane._update_clean_cues_button_enabled()

    pane._on_clean_cues_clicked()

    assert len(cue_repo.list_for_source(source_a)) == 1
    # Other video's cues are completely untouched.
    assert cue_repo.list_for_source(source_b) == cues_b


def test_clean_cues_second_click_is_idempotent(qapp_guard, tmp_path):
    cues = [
        _make_cue("c1", 0.0, 1.0, text="hello world", observation_ids=("o1",)),
        _make_cue("c2", 1.0, 2.0, text="hello world", observation_ids=("o2",)),
        _make_cue("c3", 2.0, 3.0, text="a distinct caption", observation_ids=("o3",)),
    ]
    pane, cue_repo = _make_pane(tmp_path, cues=cues)

    pane._on_clean_cues_clicked()
    first_result = list(pane.qa.cues)

    pane._on_clean_cues_clicked()
    second_result = list(pane.qa.cues)

    assert len(first_result) == len(second_result)
    for a, b in zip(
        sorted(first_result, key=lambda c: c.start_time),
        sorted(second_result, key=lambda c: c.start_time),
    ):
        assert a.id == b.id
        assert a.language_layers[0].text == b.language_layers[0].text
        assert a.review_state == b.review_state


def test_clean_cues_preserves_approved_rejected_and_needs_review_unchanged(qapp_guard, tmp_path):
    approved = _make_cue("approved", 0.0, 1.0, state=ReviewState.APPROVED, text="hello world")
    rejected = _make_cue("rejected", 1.0, 2.0, state=ReviewState.REJECTED, text="hello world")
    needs_review = _make_cue("needs_review", 2.0, 3.0, state=ReviewState.NEEDS_REVIEW, text="hello world")
    eligible = _make_cue("eligible", 3.0, 4.0, text="hello world")
    pane, cue_repo = _make_pane(
        tmp_path, cues=[approved, rejected, needs_review, eligible]
    )

    pane._on_clean_cues_clicked()

    by_id = {c.id: c for c in pane.qa.cues}
    assert by_id["approved"] == approved
    assert by_id["rejected"] == rejected
    assert by_id["needs_review"] == needs_review
    assert by_id["eligible"].review_state == ReviewState.PENDING


def test_clean_cues_leaves_multilanguage_cues_untouched(qapp_guard, tmp_path):
    multi1 = _make_multilang_cue("m1", 0.0, 1.0)
    multi2 = _make_multilang_cue("m2", 1.0, 2.0)
    pane, cue_repo = _make_pane(tmp_path, cues=[multi1, multi2])

    # Multilingual-only source: no eligible (single-language) cues exist.
    assert not pane.clean_cues_button.isEnabled()

    pane._on_clean_cues_clicked()

    assert {c.id for c in pane.qa.cues} == {"m1", "m2"}
    assert all(len(c.language_layers) == 2 for c in pane.qa.cues)


def test_clean_cues_result_stays_chronologically_ordered(qapp_guard, tmp_path):
    cues = [
        _make_cue("late", 5.0, 6.0, text="one"),
        _make_cue("early", 0.0, 1.0, text="two"),
        _make_cue("mid", 2.0, 3.0, text="three", state=ReviewState.APPROVED),
    ]
    pane, _ = _make_pane(tmp_path, cues=cues)

    pane._on_clean_cues_clicked()

    starts = [c.start_time for c in pane.qa.cues]
    assert starts == sorted(starts)


def test_export_controls_reads_cleaned_workspace_state(qapp_guard, tmp_path):
    """All four export formats share the same `get_cues` seam
    (`self.qa.cues`), so proving this callback reflects the cleaned
    result covers SRT/VTT/Readable/AI-ready export consumption without
    duplicating a per-format test."""
    cues = [
        _make_cue("c1", 0.0, 1.0, text="hello world"),
        _make_cue("c2", 1.0, 2.0, text="hello world"),
    ]
    pane, _ = _make_pane(tmp_path, cues=cues)

    pane._on_clean_cues_clicked()

    exported_cues = pane.export_controls._get_cues()
    assert exported_cues == pane.qa.cues
    assert len(exported_cues) == 1
    assert exported_cues[0].language_layers[0].text == "hello world"
