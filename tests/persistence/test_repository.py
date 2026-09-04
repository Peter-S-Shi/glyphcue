import pytest

from glyphcue.domain.cue import Cue
from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.domain.review_state import ReviewState
from glyphcue.persistence.database import connect
from glyphcue.persistence.repository import CueRepository


@pytest.fixture
def repository(tmp_path):
    conn = connect(tmp_path / "glyphcue.sqlite3")
    return CueRepository(conn)


def test_add_then_get_roundtrips_a_single_language_cue(repository):
    cue = Cue(
        id="cue-1",
        start_time=1.0,
        end_time=2.5,
        language_layers=(LanguageLayer(language="en", text="hello"),),
    )

    repository.add(cue)
    fetched = repository.get("cue-1")

    assert fetched == cue


def test_get_returns_none_for_unknown_id(repository):
    assert repository.get("missing") is None


def test_roundtrip_preserves_language_layer_order(repository):
    cue = Cue(
        id="cue-2",
        start_time=0.0,
        end_time=1.0,
        language_layers=(
            LanguageLayer(language="ja", text="こんにちは"),
            LanguageLayer(language="en", text="hello"),
        ),
    )

    repository.add(cue)
    fetched = repository.get("cue-2")

    assert fetched.language_layers[0].language == "ja"
    assert fetched.language_layers[1].language == "en"


def test_roundtrip_preserves_review_state_and_observation_ids(repository):
    cue = Cue(
        id="cue-3",
        start_time=0.0,
        end_time=1.0,
        language_layers=(
            LanguageLayer(language="en", text="hi", observation_ids=("obs-1", "obs-2")),
        ),
        review_state=ReviewState.APPROVED,
    )

    repository.add(cue)
    fetched = repository.get("cue-3")

    assert fetched.review_state is ReviewState.APPROVED
    assert fetched.language_layers[0].observation_ids == ("obs-1", "obs-2")


def test_list_all_returns_every_added_cue(repository):
    first = Cue(id="a", start_time=0.0, end_time=1.0, language_layers=(LanguageLayer(language="en", text="a"),))
    second = Cue(id="b", start_time=1.0, end_time=2.0, language_layers=(LanguageLayer(language="en", text="b"),))

    repository.add(first)
    repository.add(second)

    assert {cue.id for cue in repository.list_all()} == {"a", "b"}


def test_save_cues_for_source_and_list_for_source_roundtrips(repository):
    source_a = "video_a.mp4"
    source_b = "video_b.mp4"

    cues_a = [
        Cue(
            id="cue-a1",
            start_time=0.0,
            end_time=1.0,
            language_layers=(LanguageLayer(language="en", text="a1", observation_ids=("obs-1",)),),
            review_state=ReviewState.APPROVED,
        ),
        Cue(
            id="cue-a2",
            start_time=1.5,
            end_time=2.5,
            language_layers=(LanguageLayer(language="ja", text="a2"),),
            review_state=ReviewState.PENDING,
        ),
    ]
    cues_b = [
        Cue(
            id="cue-b1",
            start_time=0.5,
            end_time=1.5,
            language_layers=(LanguageLayer(language="zh", text="b1"),),
            review_state=ReviewState.NEEDS_REVIEW,
        ),
    ]

    repository.save_cues_for_source(source_a, cues_a)
    repository.save_cues_for_source(source_b, cues_b)

    assert repository.list_for_source(source_a) == cues_a
    assert repository.list_for_source(source_b) == cues_b
    assert repository.list_for_source("unknown_source.mp4") == []


def test_save_cues_for_source_replaces_atomically_without_fk_violation(repository):
    source_a = "video_a.mp4"
    initial_cues = [
        Cue(
            id="cue-1",
            start_time=0.0,
            end_time=1.0,
            language_layers=(LanguageLayer(language="en", text="hello"),),
        ),
        Cue(
            id="cue-2",
            start_time=2.0,
            end_time=3.0,
            language_layers=(LanguageLayer(language="en", text="world"),),
        ),
    ]
    repository.save_cues_for_source(source_a, initial_cues)

    updated_cues = [
        Cue(
            id="cue-3",
            start_time=0.5,
            end_time=1.5,
            language_layers=(LanguageLayer(language="en", text="replaced"),),
            review_state=ReviewState.APPROVED,
        ),
    ]
    repository.save_cues_for_source(source_a, updated_cues)

    assert repository.list_for_source(source_a) == updated_cues
    assert repository.get("cue-1") is None
    assert repository.get("cue-2") is None
    assert repository.get("cue-3") == updated_cues[0]


def test_delete_for_source_removes_cues_and_layers_without_fk_violation(repository):
    source_a = "video_a.mp4"
    source_b = "video_b.mp4"
    repository.save_cues_for_source(
        source_a,
        [Cue(id="cue-a", start_time=0.0, end_time=1.0, language_layers=(LanguageLayer("en", "a"),))],
    )
    repository.save_cues_for_source(
        source_b,
        [Cue(id="cue-b", start_time=0.0, end_time=1.0, language_layers=(LanguageLayer("en", "b"),))],
    )

    repository.delete_for_source(source_a)

    assert repository.list_for_source(source_a) == []
    assert len(repository.list_for_source(source_b)) == 1


def test_update_cue_state_persists_review_state(repository):
    cue = Cue(
        id="cue-update",
        start_time=0.0,
        end_time=1.0,
        language_layers=(LanguageLayer("en", "text"),),
        review_state=ReviewState.PENDING,
    )
    repository.add(cue, source_id="source.mp4")

    repository.update_cue_state("cue-update", ReviewState.APPROVED)

    fetched = repository.get("cue-update")
    assert fetched.review_state == ReviewState.APPROVED


def test_legacy_cues_with_empty_source_id_are_isolated_from_specific_sources(repository):
    legacy = Cue(id="legacy-1", start_time=0.0, end_time=1.0, language_layers=(LanguageLayer("en", "legacy"),))
    repository.add(legacy)  # legacy add without source_id

    assert repository.list_for_source("video_a.mp4") == []
    assert [c.id for c in repository.list_all()] == ["legacy-1"]

