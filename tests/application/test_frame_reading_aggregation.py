from glyphcue.application.frame_reading_aggregation import (
    aggregate_same_frame_observations,
    member_observation_ids,
)
from glyphcue.domain.observation import Observation
from glyphcue.domain.provenance import Provenance, ProvenanceKind

_PROVENANCE = Provenance(kind=ProvenanceKind.OCR_ENGINE, source="PaddleOCR")


def _obs(id_, text, start, frame_reference, geometry=None, confidence=None):
    return Observation(
        id=id_,
        text=text,
        start_time=start,
        end_time=start + 0.001,
        provenance=_PROVENANCE,
        frame_reference=frame_reference,
        geometry=geometry,
        confidence=confidence,
    )


def test_single_region_frame_passes_through_unchanged():
    observation = _obs("o1", "Hello", start=1.0, frame_reference="v.mp4@1.000000s")

    result = aggregate_same_frame_observations([observation])

    assert result == [observation]
    assert member_observation_ids(result[0]) == ("o1",)


def test_two_regions_from_the_same_frame_are_combined_into_one_reading():
    region_a = _obs("o1", "Line one", start=1.0, frame_reference="v.mp4@1.000000s")
    region_b = _obs("o2", "Line two", start=1.0, frame_reference="v.mp4@1.000000s")

    result = aggregate_same_frame_observations([region_a, region_b])

    assert len(result) == 1
    combined = result[0]
    assert combined.text == "Line oneLine two"
    assert combined.start_time == 1.0
    assert combined.end_time == 1.001
    assert member_observation_ids(combined) == ("o1", "o2")


def test_reading_order_follows_geometry_top_to_bottom():
    # Deliberately scripted out of reading order to prove the aggregator
    # reorders by position, not by input order.
    bottom = _obs(
        "o_bottom", "Second line", start=1.0, frame_reference="v.mp4@1.000000s",
        geometry=((0.0, 20.0), (10.0, 20.0), (10.0, 30.0), (0.0, 30.0)),
    )
    top = _obs(
        "o_top", "First line", start=1.0, frame_reference="v.mp4@1.000000s",
        geometry=((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)),
    )

    result = aggregate_same_frame_observations([bottom, top])

    assert result[0].text == "First lineSecond line"
    assert member_observation_ids(result[0]) == ("o_top", "o_bottom")


def test_regions_from_different_frames_are_not_combined():
    frame_one = _obs("o1", "State A", start=1.0, frame_reference="v.mp4@1.000000s")
    frame_two = _obs("o2", "State B", start=2.0, frame_reference="v.mp4@2.000000s")

    result = aggregate_same_frame_observations([frame_one, frame_two])

    assert len(result) == 2
    assert [obs.text for obs in result] == ["State A", "State B"]


def test_confidence_is_averaged_across_combined_regions():
    region_a = _obs("o1", "A", start=1.0, frame_reference="f", confidence=0.8)
    region_b = _obs("o2", "B", start=1.0, frame_reference="f", confidence=0.6)

    result = aggregate_same_frame_observations([region_a, region_b])

    assert result[0].confidence == 0.7


def test_frame_order_is_preserved_across_multiple_frames():
    frame_one_a = _obs("o1", "A1", start=1.0, frame_reference="f1")
    frame_one_b = _obs("o2", "A2", start=1.0, frame_reference="f1")
    frame_two = _obs("o3", "B", start=2.0, frame_reference="f2")

    result = aggregate_same_frame_observations([frame_one_a, frame_one_b, frame_two])

    assert [obs.text for obs in result] == ["A1A2", "B"]


def test_empty_input_produces_no_output():
    assert aggregate_same_frame_observations([]) == []
