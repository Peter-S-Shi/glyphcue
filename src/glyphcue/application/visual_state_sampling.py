from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

_DEFAULT_EDGE_THRESHOLD = 0.04
_DEFAULT_BLANK_DENSITY_THRESHOLD = 0.01
_DEFAULT_GROUP_DISTANCE_THRESHOLD = 0.06
_MAX_SIGNATURE_HEIGHT = 60
_MAX_SIGNATURE_WIDTH = 200


def _luminance(frame: np.ndarray) -> np.ndarray:
    if frame.ndim == 3:
        return (
            frame[..., 0] * 0.299 + frame[..., 1] * 0.587 + frame[..., 2] * 0.114
        ) * (1.0 / 255.0)
    return frame.astype(np.float32) * (1.0 / 255.0)


def _edge_mask(frame: np.ndarray, edge_threshold: float) -> np.ndarray:
    y = _luminance(frame)
    if y.shape[0] < 3 or y.shape[1] < 3:
        return np.zeros_like(y, dtype=bool)
    gx = np.abs(y[:, 2:] - y[:, :-2])
    gy = np.abs(y[2:, :] - y[:-2, :])
    g = gx[1:-1, :] + gy[:, 1:-1]
    return g > edge_threshold


def subtitle_visual_signature(
    roi_frame: np.ndarray,
    edge_threshold: float = _DEFAULT_EDGE_THRESHOLD,
    max_height: int = _MAX_SIGNATURE_HEIGHT,
    max_width: int = _MAX_SIGNATURE_WIDTH,
) -> np.ndarray:
    """Cheap, subtitle-focused visual signature for one ROI-cropped frame.

    A downsampled boolean text-edge mask (same luminance + gradient
    extraction as `change_detection.subtitle_structural_difference`, but
    returned as a comparable signature rather than a pairwise scalar
    diff). Two samples of the SAME subtitle state produce nearly
    identical masks no matter how far apart in time they were taken --
    unlike chaining frame-to-frame differences, comparing directly
    against an anchor signature does not accumulate drift over a long
    stable run.
    """
    if roi_frame.shape[0] > max_height or roi_frame.shape[1] > max_width:
        sy = max(1, roi_frame.shape[0] // max_height)
        sx = max(1, roi_frame.shape[1] // max_width)
        frame = roi_frame[::sy, ::sx]
    else:
        frame = roi_frame
    return _edge_mask(frame, edge_threshold)


def is_blank_signature(
    signature: np.ndarray,
    density_threshold: float = _DEFAULT_BLANK_DENSITY_THRESHOLD,
) -> bool:
    """True when a signature shows no meaningful subtitle-region text
    structure -- an explicit blank state, distinct from "some other
    stable subtitle text" (both would otherwise just be "low change")."""
    if signature.size == 0:
        return True
    return float(signature.mean()) < density_threshold


def signature_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Fraction of signature cells that disagree; 0.0 = identical,
    1.0 = fully disjoint. Shape mismatch (e.g. ROI/frame size changed)
    is treated as maximally different, never compared cell-wise."""
    if a.shape != b.shape:
        return 1.0
    return float(np.mean(a != b))


@dataclass(frozen=True)
class SampledFrame:
    """One ROI-cropped frame kept by fixed-fps sampling, already reduced
    to its visual signature."""

    index: int
    timestamp: float
    signature: np.ndarray
    is_blank: bool


@dataclass(frozen=True)
class VisualStateGroup:
    """A run of consecutive sampled frames judged to be the same visual
    subtitle state (or the same explicit blank state), collapsed to one
    representative -- the temporally middle member, chosen to avoid the
    transition-adjacent frames at either edge of the run."""

    state_kind: str  # "subtitle" | "blank"
    start_timestamp: float
    end_timestamp: float
    frame_count: int
    representative_timestamp: float
    representative_index: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "state_kind": self.state_kind,
            "start_timestamp": round(self.start_timestamp, 4),
            "end_timestamp": round(self.end_timestamp, 4),
            "frame_count": self.frame_count,
            "representative_timestamp": round(self.representative_timestamp, 4),
            "representative_index": self.representative_index,
        }


@dataclass
class VisualStateGroupingResult:
    groups: list[VisualStateGroup] = field(default_factory=list)

    @property
    def representative_timestamps(self) -> list[float]:
        return [g.representative_timestamp for g in self.groups if g.state_kind == "subtitle"]

    @property
    def subtitle_group_count(self) -> int:
        return sum(1 for g in self.groups if g.state_kind == "subtitle")

    @property
    def blank_group_count(self) -> int:
        return sum(1 for g in self.groups if g.state_kind == "blank")


def _close_group(state_kind: str, members: list[SampledFrame]) -> VisualStateGroup:
    representative = members[len(members) // 2]
    return VisualStateGroup(
        state_kind=state_kind,
        start_timestamp=members[0].timestamp,
        end_timestamp=members[-1].timestamp,
        frame_count=len(members),
        representative_timestamp=representative.timestamp,
        representative_index=representative.index,
    )


def group_visual_states(
    sampled_frames: list[SampledFrame],
    group_distance_threshold: float = _DEFAULT_GROUP_DISTANCE_THRESHOLD,
    distance: Callable[[np.ndarray, np.ndarray], float] = signature_distance,
) -> VisualStateGroupingResult:
    """Groups consecutive sampled frames into runs of one visual subtitle
    state, with blank treated as its own explicit state rather than "just
    another low-distance signature". A new subtitle frame joins the
    current subtitle run only if it stays close to that run's ANCHOR (its
    first member) -- not merely close to the previous frame -- so slow
    drift across a long stable run cannot silently accumulate into a
    false transition, one of the failure modes the frame-to-frame
    `ChangeTriggeredOcrPolicy` chain is prone to.

    `distance` defaults to the plain cell-mismatch `signature_distance`
    every Alpha round used; it is injectable so a later experiment can
    supply a comparison matched to its own signature space (e.g. Beta-N's
    shift-tolerant, mass-normalized distance over soft coverage maps)
    without changing this harness or the grouping threshold.
    """
    if not sampled_frames:
        return VisualStateGroupingResult()

    groups: list[VisualStateGroup] = []
    current_kind = "blank" if sampled_frames[0].is_blank else "subtitle"
    current_anchor = sampled_frames[0].signature
    current_members = [sampled_frames[0]]

    for frame in sampled_frames[1:]:
        if frame.is_blank:
            belongs = current_kind == "blank"
        elif current_kind == "blank":
            belongs = False
        else:
            belongs = distance(frame.signature, current_anchor) <= group_distance_threshold

        if belongs:
            current_members.append(frame)
        else:
            groups.append(_close_group(current_kind, current_members))
            current_kind = "blank" if frame.is_blank else "subtitle"
            current_anchor = frame.signature
            current_members = [frame]

    groups.append(_close_group(current_kind, current_members))
    return VisualStateGroupingResult(groups=groups)
