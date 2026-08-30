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
