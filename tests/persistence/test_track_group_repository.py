import pytest

from glyphcue.domain.roi import ROI
from glyphcue.domain.track_group import TrackGroup
from glyphcue.persistence.database import connect
from glyphcue.persistence.track_group_repository import TrackGroupRepository


@pytest.fixture
def repository(tmp_path):
    conn = connect(tmp_path / "glyphcue.sqlite3")
    return TrackGroupRepository(conn)


def test_add_then_get_roundtrips_a_track_group(repository):
    track_group = TrackGroup(
        id="tg-1", roi=ROI(x=0.1, y=0.8, width=0.8, height=0.15), languages=("ja", "en")
    )

    repository.add(track_group)
    fetched = repository.get("tg-1")

    assert fetched == track_group


def test_get_returns_none_for_unknown_id(repository):
    assert repository.get("missing") is None


def test_list_all_returns_every_added_track_group(repository):
    first = TrackGroup(id="a", roi=ROI(x=0.0, y=0.0, width=0.5, height=0.5), languages=("en",))
    second = TrackGroup(id="b", roi=ROI(x=0.5, y=0.5, width=0.5, height=0.5), languages=("ja",))

    repository.add(first)
    repository.add(second)

    assert {tg.id for tg in repository.list_all()} == {"a", "b"}
