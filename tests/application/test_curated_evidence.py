from glyphcue.application.curated_evidence import select_curated_evidence
from glyphcue.domain.observation import Observation
from glyphcue.domain.provenance import Provenance, ProvenanceKind

_PROVENANCE = Provenance(kind=ProvenanceKind.OCR_ENGINE, source="x")


def _obs(id_, text, start):
    return Observation(
        id=id_, text=text, start_time=start, end_time=start + 0.001, provenance=_PROVENANCE
    )


def test_curated_evidence_includes_the_in_point_and_out_point():
    observations = [_obs("o1", "A", 1.0), _obs("o2", "A", 2.0), _obs("o3", "A", 3.0)]

    curated = select_curated_evidence(observations, winning_text="A")

    ids = [observation.id for observation in curated]
    assert ids[0] == "o1"
    assert ids[-1] == "o3"


def test_curated_evidence_includes_disagreement_not_just_agreeing_samples():
    observations = [
        _obs("o1", "Hello world", 1.0),
        _obs("o2", "Hallo world", 2.0),  # the outlier
        _obs("o3", "Hello world", 3.0),
        _obs("o4", "Hello world", 4.0),
    ]

    curated = select_curated_evidence(observations, winning_text="Hello world")

    ids = {observation.id for observation in curated}
    assert "o2" in ids


def test_curated_evidence_does_not_include_every_redundant_stable_observation():
    # Ten identical, agreeing observations -- curated should not just
    # dump all ten (DESIGN.md section 19: relevance over volume).
    observations = [_obs(f"o{i}", "Stable", float(i)) for i in range(10)]

    curated = select_curated_evidence(observations, winning_text="Stable")

    assert len(curated) < len(observations)


def test_curated_evidence_handles_a_single_observation():
    observations = [_obs("o1", "Only one", 1.0)]

    curated = select_curated_evidence(observations, winning_text="Only one")

    assert [observation.id for observation in curated] == ["o1"]


def test_curated_evidence_never_drops_evidence_permanently():
    # Full evidence must remain accessible -- select_curated_evidence
    # only picks a DEFAULT subset; it never claims to be the only copy.
    observations = [_obs(f"o{i}", "Stable", float(i)) for i in range(10)]

    curated = select_curated_evidence(observations, winning_text="Stable")

    assert set(observation.id for observation in curated).issubset(
        {observation.id for observation in observations}
    )
