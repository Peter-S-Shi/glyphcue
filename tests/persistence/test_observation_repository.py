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

    repository.add(observation, evidence_run_id="run-1")
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

    repository.add(observation, evidence_run_id="run-1")
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

    repository.add(second, evidence_run_id="run-1")
    repository.add(first, evidence_run_id="run-1")

    assert [obs.id for obs in repository.list_all()] == ["obs-1", "obs-2"]


def test_list_for_run_returns_only_observations_from_that_run(repository):
    run_1_obs = Observation(
        id="obs-1",
        text="run one",
        start_time=1.0,
        end_time=1.001,
        provenance=Provenance(kind=ProvenanceKind.OCR_ENGINE, source="PaddleOCR"),
    )
    run_2_obs = Observation(
        id="obs-2",
        text="run two",
        start_time=2.0,
        end_time=2.001,
        provenance=Provenance(kind=ProvenanceKind.OCR_ENGINE, source="PaddleOCR"),
    )

    repository.add(run_1_obs, evidence_run_id="run-1")
    repository.add(run_2_obs, evidence_run_id="run-2")

    assert [obs.id for obs in repository.list_for_run("run-1")] == ["obs-1"]
    assert [obs.id for obs in repository.list_for_run("run-2")] == ["obs-2"]


def test_list_for_run_returns_empty_for_an_unknown_run(repository):
    assert repository.list_for_run("no-such-run") == []


def test_list_for_run_orders_by_start_time(repository):
    later = Observation(
        id="obs-later",
        text="later",
        start_time=5.0,
        end_time=5.001,
        provenance=Provenance(kind=ProvenanceKind.OCR_ENGINE, source="PaddleOCR"),
    )
    earlier = Observation(
        id="obs-earlier",
        text="earlier",
        start_time=1.0,
        end_time=1.001,
        provenance=Provenance(kind=ProvenanceKind.OCR_ENGINE, source="PaddleOCR"),
    )

    repository.add(later, evidence_run_id="run-1")
    repository.add(earlier, evidence_run_id="run-1")

    assert [obs.id for obs in repository.list_for_run("run-1")] == ["obs-earlier", "obs-later"]


def test_cancelled_partial_evidence_stays_scoped_to_its_run(repository):
    # A cancelled job's partial evidence still belongs to the run it was
    # produced in -- re-running later must not merge into the same
    # bucket as a prior (possibly partial) run.
    partial = Observation(
        id="obs-partial",
        text="partial from cancelled run",
        start_time=1.0,
        end_time=1.001,
        provenance=Provenance(kind=ProvenanceKind.OCR_ENGINE, source="PaddleOCR"),
    )
    repository.add(partial, evidence_run_id="run-cancelled")

    rerun = Observation(
        id="obs-rerun",
        text="full evidence from rerun",
        start_time=1.0,
        end_time=1.001,
        provenance=Provenance(kind=ProvenanceKind.OCR_ENGINE, source="PaddleOCR"),
    )
    repository.add(rerun, evidence_run_id="run-2")

    assert [obs.id for obs in repository.list_for_run("run-cancelled")] == ["obs-partial"]
    assert [obs.id for obs in repository.list_for_run("run-2")] == ["obs-rerun"]


def test_add_with_source_id_and_list_for_source(repository):
    obs_a1 = Observation(id="obs-a1", text="a1", start_time=1.0, end_time=1.1, provenance=Provenance(ProvenanceKind.OCR_ENGINE, "source"))
    obs_a2 = Observation(id="obs-a2", text="a2", start_time=2.0, end_time=2.1, provenance=Provenance(ProvenanceKind.OCR_ENGINE, "source"))
    obs_b1 = Observation(id="obs-b1", text="b1", start_time=0.5, end_time=0.6, provenance=Provenance(ProvenanceKind.OCR_ENGINE, "source"))

    repository.add(obs_a1, evidence_run_id="run-1", source_id="source_a.mp4")
    repository.add(obs_a2, evidence_run_id="run-2", source_id="source_a.mp4")
    repository.add(obs_b1, evidence_run_id="run-3", source_id="source_b.mp4")

    assert [obs.id for obs in repository.list_for_source("source_a.mp4")] == ["obs-a1", "obs-a2"]
    assert [obs.id for obs in repository.list_for_source("source_b.mp4")] == ["obs-b1"]
    assert repository.list_for_source("unknown.mp4") == []


def test_get_by_ids_returns_dictionary_of_matching_observations(repository):
    obs_1 = Observation(id="obs-1", text="1", start_time=1.0, end_time=1.1, provenance=Provenance(ProvenanceKind.OCR_ENGINE, "source"))
    obs_2 = Observation(id="obs-2", text="2", start_time=2.0, end_time=2.1, provenance=Provenance(ProvenanceKind.OCR_ENGINE, "source"))
    obs_3 = Observation(id="obs-3", text="3", start_time=3.0, end_time=3.1, provenance=Provenance(ProvenanceKind.OCR_ENGINE, "source"))

    repository.add(obs_1, evidence_run_id="run-1", source_id="source.mp4")
    repository.add(obs_2, evidence_run_id="run-1", source_id="source.mp4")
    repository.add(obs_3, evidence_run_id="run-1", source_id="source.mp4")

    result = repository.get_by_ids(["obs-1", "obs-3", "obs-missing"])
    assert result == {"obs-1": obs_1, "obs-3": obs_3}


