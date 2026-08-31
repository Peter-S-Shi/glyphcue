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
    processing_end_time: float | None = None,
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

    `processing_end_time` should be the real end of the range M4
    actually analyzed for this run (e.g. `probe_media(path)
    .duration_seconds`, or the resolved end of the `ProcessingRange`
    used for the job) -- the caller who ran the M4 job knows this;
    `reconstruct_cues_with_consensus` cannot derive it from Observations
    alone. Passing it gives the final reconstructed Cue an honest
    boundary instead of a ~1ms instant-marker fallback.
    """
    observations = observation_repository.list_for_run(evidence_run_id)
    return reconstruct_cues_with_consensus(
        observations,
        similarity_threshold=similarity_threshold,
        processing_end_time=processing_end_time,
    )
