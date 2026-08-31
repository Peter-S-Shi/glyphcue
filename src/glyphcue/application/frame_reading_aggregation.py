from __future__ import annotations

from glyphcue.domain.observation import Observation
from glyphcue.domain.provenance import Provenance

_MEMBER_ID_SEPARATOR = "\x1f"
_MEMBER_IDS_DETAIL_KEY = "member_observation_ids"


def aggregate_same_frame_observations(observations: list[Observation]) -> list[Observation]:
    """Combines Observations that came from the same physical OCR frame
    into one reading per frame, in stable reading order, before any
    cross-frame consensus runs.

    M4's `OcrEngine.recognize()` can return multiple `OcrTextRegion`s for
    a single frame (e.g. a two-line subtitle detected as two boxes), and
    `build_ocr_evidence_job` creates one Observation per region -- all
    sharing the same `frame_reference` (and `start_time`). Multi-frame
    consensus must never mistake these simultaneous regions of one frame
    for sequential time states, so this groups by `frame_reference`
    (each Observation without one is treated as its own single-member
    group -- non-OCR provenance, e.g. subtitle-file import, has no
    frame concept) and joins each group's text top-to-bottom by
    geometry (falling back to original order when geometry is
    unavailable, via a stable sort). Every contributing Observation's id
    is preserved -- see `member_observation_ids` -- even though the
    combined reading gets one new id.
    """
    if not observations:
        return []

    groups: dict[str, list[Observation]] = {}
    order: list[str] = []
    for observation in observations:
        key = observation.frame_reference if observation.frame_reference else f"__no_frame__{observation.id}"
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(observation)

    aggregated: list[Observation] = []
    for key in order:
        group = groups[key]
        aggregated.append(group[0] if len(group) == 1 else _combine(group))
    return aggregated


def member_observation_ids(observation: Observation) -> tuple[str, ...]:
    """The original OCR-region Observation ids that contributed to
    `observation` -- either just its own id (no aggregation happened)
    or every region's id, in reading order (set by
    `aggregate_same_frame_observations`)."""
    joined = observation.provenance.detail.get(_MEMBER_IDS_DETAIL_KEY)
    if joined:
        return tuple(joined.split(_MEMBER_ID_SEPARATOR))
    return (observation.id,)


def _reading_order_key(observation: Observation) -> tuple[float, float]:
    if observation.geometry:
        xs = [point[0] for point in observation.geometry]
        ys = [point[1] for point in observation.geometry]
        return (min(ys), min(xs))
    return (0.0, 0.0)  # no geometry: stable sort keeps original scripted/detection order


def _combine(group: list[Observation]) -> Observation:
    ordered = sorted(group, key=_reading_order_key)  # stable: ties keep original order
    combined_text = "".join(observation.text for observation in ordered)

    confidences = [observation.confidence for observation in ordered if observation.confidence is not None]
    combined_confidence = sum(confidences) / len(confidences) if confidences else None

    first = ordered[0]
    detail = dict(first.provenance.detail)
    detail[_MEMBER_IDS_DETAIL_KEY] = _MEMBER_ID_SEPARATOR.join(
        observation.id for observation in ordered
    )

    return Observation(
        id=f"combined-{first.id}",
        text=combined_text,
        start_time=first.start_time,
        end_time=first.end_time,
        provenance=Provenance(kind=first.provenance.kind, source=first.provenance.source, detail=detail),
        language=first.language,
        confidence=combined_confidence,
        roi=first.roi,
        geometry=None,  # a joined multi-region reading has no single polygon
        frame_reference=first.frame_reference,
    )
