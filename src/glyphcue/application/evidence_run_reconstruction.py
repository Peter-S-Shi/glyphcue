from __future__ import annotations

from glyphcue.application.consensus_reconstruction import (
    ConsensusDiagnostics,
    reconstruct_cues_with_consensus,
)
from glyphcue.domain.cue import Cue
from glyphcue.persistence.observation_repository import ObservationRepository

_DEFAULT_SIMILARITY_THRESHOLD = 0.5


def reconstruct_cues_for_evidence_run(
    observation_repository: ObservationRepository,
    evidence_run_id: str,
    *,
    similarity_threshold: float = _DEFAULT_SIMILARITY_THRESHOLD,
) -> tuple[list[Cue], list[ConsensusDiagnostics]]:
    """The real M4 -> M5 seam: fetch exactly one evidence run's
    Observations and reconstruct Cues from them.

    This is the only place M5 code should call into
    `ObservationRepository` -- always via `list_for_run`, never
    `list_all`, so Observations from different videos or different
    re-runs of the same video can never be silently aggregated into one
    reconstruction. See `ObservationRepository.list_for_run` and
    `reconstruct_cues_with_consensus` for the two halves of this
    contract.
    """
    observations = observation_repository.list_for_run(evidence_run_id)
    return reconstruct_cues_with_consensus(observations, similarity_threshold=similarity_threshold)
