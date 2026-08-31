import pytest

from glyphcue.domain.observation import Observation
from glyphcue.domain.provenance import Provenance, ProvenanceKind
from glyphcue.domain.roi import ROI


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


def test_observation_defaults_evidence_fields_to_none():
    observation = Observation(
        id="obs-5",
        text="Hello",
        start_time=0.0,
        end_time=1.0,
        provenance=_provenance(),
    )

    assert observation.confidence is None
    assert observation.roi is None
    assert observation.geometry is None
    assert observation.frame_reference is None


def test_observation_holds_ocr_evidence_fields():
    roi = ROI(x=0.1, y=0.8, width=0.8, height=0.15)
    geometry = ((1.0, 2.0), (10.0, 2.0), (10.0, 20.0), (1.0, 20.0))

    observation = Observation(
        id="obs-6",
        text="raw ocr text",
        start_time=1.0,
        end_time=1.001,
        provenance=Provenance(kind=ProvenanceKind.OCR_ENGINE, source="PaddleOCR"),
        language="zh",
        confidence=0.97,
        roi=roi,
        geometry=geometry,
        frame_reference="video.mp4@1.000000s",
    )

    assert observation.confidence == 0.97
    assert observation.roi == roi
    assert observation.geometry == geometry
    assert observation.frame_reference == "video.mp4@1.000000s"
