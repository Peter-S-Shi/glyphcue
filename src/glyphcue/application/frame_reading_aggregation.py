from __future__ import annotations

from typing import Callable

from glyphcue.domain.observation import Observation
from glyphcue.domain.provenance import Provenance

_MEMBER_ID_SEPARATOR = "\x1f"
_MEMBER_IDS_DETAIL_KEY = "member_observation_ids"

ReadingOrderKey = Callable[[Observation], tuple[float, float]]


def aggregate_same_frame_observations(
    observations: list[Observation],
    *,
    reading_order_key: ReadingOrderKey | None = None,
) -> list[Observation]:
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
    unavailable, via a stable sort). Regions whose vertical extent
    (from `geometry`) doesn't overlap at all with the previous region's
    are joined with a real newline ("\n") -- genuine evidence of a
    separate visual line, e.g. a two-line subtitle; without geometry for
    either region there's no such evidence, so they're joined directly
    with no separator. Every contributing Observation's id is preserved
    -- see `member_observation_ids` -- even though the combined reading
    gets one new id.

    `reading_order_key` overrides the default geometry-based sort used to
    decide join order (never the geometry-based newline decision, which
    always uses each observation's own real y-range regardless of this
    override). Milestone 6's multilingual path needs this: it already
    computes a canonical, language-based order once
    (`multilingual_reconstruction._canonicalize_frame_order`) so that a
    stable bilingual subtitle whose physical layer POSITIONS happen to
    swap between frames still joins into the same string every frame --
    the default geometry sort would silently re-derive (and disagree
    with) that canonical order from each frame's own raw positions,
    reintroducing the exact false state-boundary this parameter exists to
    prevent. The single-language M5 caller passes nothing and keeps the
    original geometry-only behavior unchanged.
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
        aggregated.append(
            group[0] if len(group) == 1 else _combine(group, reading_order_key)
        )
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


def _y_range(observation: Observation) -> tuple[float, float] | None:
    if not observation.geometry:
        return None
    ys = [point[1] for point in observation.geometry]
    return (min(ys), max(ys))


def _on_a_new_visual_line(previous_y_range: tuple[float, float] | None, current_y_range: tuple[float, float] | None) -> bool:
    """Whether `current_y_range` is a real, visually distinct line below
    `previous_y_range` -- i.e. their vertical extents don't overlap at
    all. Without geometry for either region, there's no evidence of a
    line break, so this defaults to False (same behavior as before
    geometry-aware joining existed) rather than guessing."""
    if previous_y_range is None or current_y_range is None:
        return False
    previous_min, previous_max = previous_y_range
    current_min, current_max = current_y_range
    overlap = min(previous_max, current_max) - max(previous_min, current_min)
    return overlap <= 0


def _combine(group: list[Observation], reading_order_key: ReadingOrderKey | None) -> Observation:
    ordered = sorted(group, key=reading_order_key or _reading_order_key)  # stable: ties keep original order

    parts: list[str] = []
    previous_y_range: tuple[float, float] | None = None
    for observation in ordered:
        current_y_range = _y_range(observation)
        if parts and _on_a_new_visual_line(previous_y_range, current_y_range):
            parts.append("\n")
        parts.append(observation.text)
        previous_y_range = current_y_range
    combined_text = "".join(parts)

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
