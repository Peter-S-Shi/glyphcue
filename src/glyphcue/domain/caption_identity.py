"""Versioned Hybrid evidence, independent of OCR vendors and storage.

An envelope asserts visual similarity only. Probe support and change brackets
are observations, never inferred continuous subtitle timing. All coordinates
are ROI-image pixels; frame refs locate the original source PTS.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass

from glyphcue.domain.observation import Observation

CAPTION_IDENTITY_VERSION = "caption-identity-v1"
CONTRACT_KEY = "caption_identity_contract"
PAYLOAD_KEY = "caption_identity_payload"
ROLE_KEY = "caption_identity_role"
ENVELOPE_KEY = "caption_envelope_id"
REPRESENTATIVE_PTS_KEY = "representative_pts"
OBSERVED_STATE_START_KEY = "observed_state_start"
OBSERVED_STATE_END_KEY = "observed_state_end"


@dataclass(frozen=True)
class FrameObservationRef:
    index: int
    pts: float
    frame_reference: str


@dataclass(frozen=True)
class CoarseEnvelope:
    id: str
    observed_start: float
    observed_end: float
    representative_pts: float
    observations: tuple[FrameObservationRef, ...]

    def __post_init__(self) -> None:
        pts = tuple(ref.pts for ref in self.observations)
        indices = tuple(ref.index for ref in self.observations)
        if (not pts or any(not math.isfinite(p) or p < 0 for p in pts)
                or any(a >= b for a, b in zip(pts, pts[1:]))
                or any(a >= b for a, b in zip(indices, indices[1:]))):
            raise ValueError("CoarseEnvelope requires ordered, unique observation refs")
        if (self.observed_start != pts[0] or self.observed_end != pts[-1]
                or self.representative_pts not in pts):
            raise ValueError("CoarseEnvelope bounds/representative must refer to observed PTS")


@dataclass(frozen=True)
class CaptionBlock:
    text: str
    bounds: tuple[float, float, float, float] | None
    region_ids: tuple[str, ...]


@dataclass(frozen=True)
class CaptionProbe:
    observation_index: int
    pts: float
    reason: str
    raw_region_ids: tuple[str, ...]
    blocks: tuple[CaptionBlock, ...]
    alternatives: tuple[CaptionBlock, ...]
    selected_text: str | None
    partition_ambiguous: bool = False

    def __post_init__(self) -> None:
        if any(not set(b.region_ids) <= set(self.raw_region_ids) for b in self.blocks + self.alternatives):
            raise ValueError("Caption block references regions outside its raw probe")
        if self.selected_text is not None:
            supported = (len(self.alternatives) == 1 and self.alternatives[0].text == self.selected_text)
            blank = not self.alternatives and self.selected_text == ""
            if self.partition_ambiguous or not (supported or blank):
                raise ValueError("Caption selected text must have one unambiguous supporting block")


@dataclass(frozen=True)
class TranscriptionIdentity:
    selected_text: str | None
    support_pts: tuple[float, ...]
    alternatives: tuple[str, ...]


@dataclass(frozen=True)
class CaptionIdentityEvidence:
    version: str
    envelope: CoarseEnvelope
    probes: tuple[CaptionProbe, ...]
    identities: tuple[TranscriptionIdentity, ...]
    boundary_brackets: tuple[tuple[float, float], ...]
    unqueried_intervals: tuple[tuple[float, float], ...]
    all_observations_probed: bool
    correspondence_ambiguous: bool
    selection_ambiguous: bool
    stop_reason: str
    probe_budget: int
    selection_rationale: str
    coordinate_space: str = "roi_pixels"

    def __post_init__(self) -> None:
        if self.version != CAPTION_IDENTITY_VERSION or self.coordinate_space != "roi_pixels":
            raise ValueError("Unsupported caption identity evidence version/coordinate space")
        refs = {ref.index: ref.pts for ref in self.envelope.observations}
        pts = tuple(p.pts for p in self.probes)
        if (any(refs.get(p.observation_index) != p.pts for p in self.probes)
                or any(a >= b for a, b in zip(pts, pts[1:]))):
            raise ValueError("Caption probes must reference ordered envelope observations")
        if self.probe_budget < 3 or len(self.probes) > self.probe_budget:
            raise ValueError("Invalid caption probe resource budget")
        if self.all_observations_probed != (len(self.probes) == len(refs)):
            raise ValueError("Caption probe completeness contradicts observation refs")
        if self.correspondence_ambiguous and any(p.selected_text is not None for p in self.probes):
            raise ValueError("Non-unique correspondence cannot authorize selected text")

    def to_json(self) -> str:
        # JSON escapes control characters, including the legacy provenance
        # storage delimiter. Raw OCR text is never interpolated into that wire.
        return json.dumps(asdict(self), ensure_ascii=True, allow_nan=False)

    @classmethod
    def from_json(cls, payload: str) -> CaptionIdentityEvidence:
        data = json.loads(payload)
        if data["version"] != CAPTION_IDENTITY_VERSION:
            raise ValueError("Unsupported caption identity evidence version")
        envelope = dict(data["envelope"])
        envelope["observations"] = tuple(FrameObservationRef(**r) for r in envelope["observations"])

        def block(value):
            return CaptionBlock(value["text"], tuple(value["bounds"]) if value["bounds"] else None,
                                tuple(value["region_ids"]))

        probes = tuple(CaptionProbe(
            p["observation_index"], p["pts"], p["reason"], tuple(p["raw_region_ids"]),
            tuple(block(b) for b in p["blocks"]), tuple(block(b) for b in p["alternatives"]),
            p["selected_text"], p.get("partition_ambiguous", False),
        ) for p in data["probes"])
        identities = tuple(TranscriptionIdentity(
            i["selected_text"], tuple(i["support_pts"]), tuple(i["alternatives"]),
        ) for i in data["identities"])
        return cls(
            data["version"], CoarseEnvelope(**envelope), probes, identities,
            tuple(tuple(p) for p in data["boundary_brackets"]),
            tuple(tuple(p) for p in data["unqueried_intervals"]),
            data["all_observations_probed"], data["correspondence_ambiguous"],
            data["selection_ambiguous"], data["stop_reason"], data["probe_budget"],
            data["selection_rationale"], data["coordinate_space"],
        )


def caption_identity_evidence(observation: Observation) -> CaptionIdentityEvidence | None:
    """Read the typed companion from a persisted public evidence record.

    Unknown versions raise, rather than falling back to legacy aggregation.
    Raw probes carry the same version marker but do not carry the companion.
    """
    detail = observation.provenance.detail
    version = detail.get(CONTRACT_KEY)
    if version is None:
        return None
    if version != CAPTION_IDENTITY_VERSION:
        raise ValueError("Unsupported caption identity evidence version")
    if detail.get(ROLE_KEY) != "envelope":
        return None
    return CaptionIdentityEvidence.from_json(detail[PAYLOAD_KEY])
