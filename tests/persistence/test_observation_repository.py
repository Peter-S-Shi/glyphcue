import pytest

from glyphcue.domain.observation import Observation
from glyphcue.domain.provenance import Provenance, ProvenanceKind
from glyphcue.domain.roi import ROI
from glyphcue.persistence.database import connect
from glyphcue.persistence.observation_repository import ObservationRepository


@pytest.fixture
def repository(tmp_path):
    conn = connect(tmp_path / "glyphcue.sqlite3")
    return ObservationRepository(conn)


def _ocr_observation(id_: str) -> Observation:
    return Observation(
        id=id_,
        text="raw ocr text",
        start_time=1.0,
        end_time=1.001,
        provenance=Provenance(
            kind=ProvenanceKind.OCR_ENGINE,
            source="PaddleOCR",
            detail={"engine_version": "3.7.0", "backend": "cpu"},
        ),
        language="zh",
        confidence=0.97,
        roi=ROI(x=0.1, y=0.8, width=0.8, height=0.15),
        geometry=((1.0, 2.0), (10.0, 2.0), (10.0, 20.0), (1.0, 20.0)),
        frame_reference="video.mp4@1.000000s",
    )


def test_add_then_get_roundtrips_a_full_ocr_observation(repository):
    observation = _ocr_observation("obs-1")

    repository.add(observation)
    fetched = repository.get("obs-1")

    assert fetched == observation


def test_add_then_get_roundtrips_an_observation_without_optional_evidence_fields(repository):
    observation = Observation(
        id="obs-2",
        text="from subtitle file",
        start_time=0.0,
        end_time=1.0,
        provenance=Provenance(kind=ProvenanceKind.SUBTITLE_IMPORT, source="input.srt"),
    )

    repository.add(observation)
    fetched = repository.get("obs-2")

    assert fetched == observation
    assert fetched.confidence is None
    assert fetched.roi is None
    assert fetched.geometry is None
    assert fetched.frame_reference is None


def test_get_returns_none_for_unknown_id(repository):
    assert repository.get("missing") is None


def test_list_all_returns_every_added_observation_ordered_by_start_time(repository):
    first = _ocr_observation("obs-1")
    second = Observation(
        id="obs-2",
        text="later",
        start_time=5.0,
        end_time=5.001,
        provenance=Provenance(kind=ProvenanceKind.OCR_ENGINE, source="PaddleOCR"),
    )

    repository.add(second)
    repository.add(first)

    assert [obs.id for obs in repository.list_all()] == ["obs-1", "obs-2"]
