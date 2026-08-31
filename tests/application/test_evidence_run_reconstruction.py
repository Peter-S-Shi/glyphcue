import pytest

from glyphcue.application.evidence_run_reconstruction import reconstruct_cues_for_evidence_run
from glyphcue.domain.observation import Observation
from glyphcue.domain.provenance import Provenance, ProvenanceKind
from glyphcue.persistence.database import connect
from glyphcue.persistence.observation_repository import ObservationRepository

_PROVENANCE = Provenance(kind=ProvenanceKind.OCR_ENGINE, source="PaddleOCR")


@pytest.fixture
def repository(tmp_path):
    conn = connect(tmp_path / "glyphcue.sqlite3")
    return ObservationRepository(conn)


def _obs(id_, text, start):
    return Observation(
        id=id_, text=text, start_time=start, end_time=start + 0.001, provenance=_PROVENANCE
    )


def test_reconstructs_cues_from_only_the_given_evidence_run(repository):
    repository.add(_obs("o1", "Run one text", start=1.0), evidence_run_id="run-1")
    repository.add(_obs("o2", "Run one text", start=2.0), evidence_run_id="run-1")
    repository.add(_obs("o3", "Completely unrelated run two content", start=1.5), evidence_run_id="run-2")

    cues, diagnostics = reconstruct_cues_for_evidence_run(repository, "run-1")

    assert len(cues) == 1
    assert cues[0].language_layers[0].text == "Run one text"
    assert cues[0].language_layers[0].observation_ids == ("o1", "o2")
    assert len(diagnostics) == 1


def test_never_aggregates_across_evidence_run_ids(repository):
    repository.add(_obs("o1", "Alpha state text here", start=1.0), evidence_run_id="run-a")
    repository.add(_obs("o2", "Beta state text content", start=1.0), evidence_run_id="run-b")

    cues_a, _ = reconstruct_cues_for_evidence_run(repository, "run-a")
    cues_b, _ = reconstruct_cues_for_evidence_run(repository, "run-b")

    assert [c.language_layers[0].text for c in cues_a] == ["Alpha state text here"]
    assert [c.language_layers[0].text for c in cues_b] == ["Beta state text content"]


def test_unknown_evidence_run_id_produces_no_cues(repository):
    cues, diagnostics = reconstruct_cues_for_evidence_run(repository, "no-such-run")

    assert cues == []
    assert diagnostics == []
