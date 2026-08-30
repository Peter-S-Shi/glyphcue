import pytest

from glyphcue.domain.observation import Observation
from glyphcue.domain.provenance import Provenance, ProvenanceKind


def _provenance() -> Provenance:
    return Provenance(kind=ProvenanceKind.SUBTITLE_IMPORT, source="input.srt")


def test_observation_holds_text_and_timing():
    observation = Observation(
        id="obs-1",
        text="Hello",
        start_time=1.0,
        end_time=2.5,
        provenance=_provenance(),
    )

    assert observation.text == "Hello"
    assert observation.start_time == 1.0
    assert observation.end_time == 2.5
    assert observation.language is None


def test_observation_rejects_end_before_start():
    with pytest.raises(ValueError):
        Observation(
            id="obs-2",
            text="Hello",
            start_time=2.0,
            end_time=1.0,
            provenance=_provenance(),
        )


def test_observation_rejects_negative_start_time():
    with pytest.raises(ValueError):
        Observation(
            id="obs-3",
            text="Hello",
            start_time=-0.5,
            end_time=1.0,
            provenance=_provenance(),
        )


def test_observation_is_immutable():
    observation = Observation(
        id="obs-4",
        text="Hello",
        start_time=0.0,
        end_time=1.0,
        provenance=_provenance(),
    )

    with pytest.raises(AttributeError):
        observation.text = "Changed"
