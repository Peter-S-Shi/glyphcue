from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from glyphcue.application.consensus_reconstruction import ConsensusDiagnostics
    from glyphcue.application.multilingual_reconstruction import MultilingualDiagnostics
    from glyphcue.application.reconstruction import PathBDiagnostics
    from glyphcue.domain.observation import Observation

_HIGH_THRESHOLD = 0.66
_MEDIUM_THRESHOLD = 0.33
_LOW_CONFIDENCE_THRESHOLD = 0.9
"""Below this mean OCR confidence, evidence is worth flagging for
review; at or above it, a routine sub-1.0 reading (real OCR confidence
is rarely exactly 1.0) is not itself review-worthy on its own -- an
explainable cutoff, not silent noise-chasing, mirroring M5's own
`similarity_threshold` pattern."""
"""Review Priority is a triage heuristic, never a calibrated
probability (ROADMAP M7 / DESIGN.md section 21). `score` is a plain
0..1 capped sum of independently-explainable component contributions --
not a statistically meaningful percentage of anything. These
thresholds bucket that heuristic into the accepted UI vocabulary
("Review Priority: High/Medium/Low", "No Review Flags") rather than
ever rendering the raw score as if it were a confidence percentage."""


@dataclass(frozen=True)
class ReviewSignals:
    """The minimal, explainable per-Cue signal bundle Review Priority
    scores from -- deliberately independent of `ConsensusDiagnostics`
    (M5) / `MultilingualDiagnostics` (M6)'s own shapes, so the scorer
    works identically for Path A (OCR) and Path B (subtitle-import)
    Cues, which don't share a diagnostics type. See
    `review_signals_from_consensus_diagnostics` /
    `review_signals_from_multilingual_diagnostics` for the adapters
    that build this from each path's real reconstruction diagnostics.
    """

    cue_id: str
    mean_ocr_confidence: float | None
    """Average OCR-engine confidence across this Cue's supporting
    Observations, or None when no confidence signal exists at all
    (e.g. a Path B subtitle-import Cue, or a Path A Observation whose
    engine never reported one) -- None must never be treated as 0.0
    (maximally suspicious); it means "no signal," not "bad signal.\""""
    had_disagreement: bool
    """Whether the reconstruction's own supporting evidence disagreed
    (M5's `ConsensusDiagnostics.had_disagreement`, or an equivalent
    per-language check for a multilingual Cue) -- real evidence of
    cross-frame/cross-source inconsistency, not a guess."""
    missing_language_count: int
    """Number of a multilingual Cue's expected language layers with no
    supporting evidence at all (M6's `MultilingualDiagnostics.missing_languages`).
    Always 0 for a single-language Cue."""
    ambiguous_language_count: int
    """Number of language layers M6's layer-separation algorithm could
    only place via its geometry-only fallback, not a decisive
    classification (`MultilingualDiagnostics.ambiguous_languages`).
    Always 0 for a single-language Cue."""
    disagreement_detail: tuple[str, str] | None = None
    """Optional `(component_name, explanation)` override for the
    `had_disagreement` component, used verbatim instead of the default
    OCR-majority-vote wording. `had_disagreement` means something
    genuinely different per path -- M5's real cross-frame majority vote
    for Path A, vs M8's "reconstruction could not confidently resolve
    this Cue" for Path B -- and reusing Path A's hardcoded explanation
    text for a Path B Cue would be a FALSE explanation, not just a
    generic one. None (the default) keeps the original Path A wording,
    so M5/M6 callers are unaffected."""


@dataclass(frozen=True)
class ReviewPriorityComponent:
    """One explainable contributor to a Cue's Review Priority score --
    this is what answers "why is this ranked here?" (ROADMAP M7:
    "every Cue must be able to explain why it's ranked here")."""

    name: str
    contribution: float
    explanation: str


@dataclass(frozen=True)
class ReviewPriority:
    """A transparent triage ranking for one Cue -- NOT a probability
    (ROADMAP M7 / DESIGN.md section 21: never display as "92%
    confidence" or any other calibrated-sounding percentage). `score`
    is the plain capped sum of `components`' contributions, always
    reproducible from them; `level` is the DESIGN.md-accepted coarse
    vocabulary ("High"/"Medium"/"Low"/"None") for UI surfaces that
    don't want to show a raw number."""

    cue_id: str
    score: float
    level: str
    components: tuple[ReviewPriorityComponent, ...]


def _level_for_score(score: float) -> str:
    if score >= _HIGH_THRESHOLD:
        return "High"
    if score >= _MEDIUM_THRESHOLD:
        return "Medium"
    if score > 0.0:
        return "Low"
    return "None"


def compute_review_priority(signals: ReviewSignals) -> ReviewPriority:
    """Combines `signals` into one explainable `ReviewPriority`.

    Every component that contributes is included in `components` with
    its own plain-language `explanation` -- there is no hidden
    weighting a user can't see the reason for. A signal that doesn't
    apply (e.g. no OCR confidence available) contributes no component
    at all, rather than a fabricated 0 or neutral value standing in for
    missing evidence.
    """
    components: list[ReviewPriorityComponent] = []

    if signals.mean_ocr_confidence is not None and signals.mean_ocr_confidence < _LOW_CONFIDENCE_THRESHOLD:
        confidence_contribution = (
            _LOW_CONFIDENCE_THRESHOLD - signals.mean_ocr_confidence
        ) / _LOW_CONFIDENCE_THRESHOLD
        components.append(
            ReviewPriorityComponent(
                name="ocr_confidence",
                contribution=min(1.0, confidence_contribution),
                explanation=(
                    f"Mean OCR-engine confidence across supporting evidence is "
                    f"{signals.mean_ocr_confidence:.2f} -- lower confidence readings "
                    "are more worth checking."
                ),
            )
        )

    if signals.had_disagreement:
        if signals.disagreement_detail is not None:
            component_name, explanation = signals.disagreement_detail
        else:
            component_name = "cross_frame_disagreement"
            explanation = (
                "Supporting observations disagreed with each other during "
                "reconstruction -- the winning text was chosen by majority vote, "
                "not unanimous agreement."
            )
        components.append(
            ReviewPriorityComponent(
                name=component_name,
                contribution=1.0,
                explanation=explanation,
            )
        )

    if signals.missing_language_count > 0:
        components.append(
            ReviewPriorityComponent(
                name="missing_language_layer",
                contribution=1.0,
                explanation=(
                    f"{signals.missing_language_count} expected language layer(s) have "
                    "no supporting evidence in this Cue."
                ),
            )
        )

    if signals.ambiguous_language_count > 0:
        components.append(
            ReviewPriorityComponent(
                name="ambiguous_language_layer",
                contribution=1.0,
                explanation=(
                    f"{signals.ambiguous_language_count} language layer(s) could only be "
                    "placed by a geometry-only fallback, not a decisive script/hint match."
                ),
            )
        )

    # Sum-and-cap, not an average: ROADMAP M7's monotonic invariant --
    # adding evidence of ANY new, independently-explainable problem must
    # never LOWER a Cue's score. An average violates this (a strong
    # signal averaged with a weak one drops below the strong signal
    # alone); a capped sum of non-negative contributions cannot -- each
    # additional component can only add to the running total before the
    # `min(1.0, ...)` cap is applied, so the score is monotonic
    # non-decreasing in the number and strength of contributing signals
    # by construction, not by tuning.
    score = min(1.0, sum(component.contribution for component in components))
    return ReviewPriority(
        cue_id=signals.cue_id,
        score=score,
        level=_level_for_score(score),
        components=tuple(components),
    )


def _mean_confidence(observations: list["Observation"]) -> float | None:
    confidences = [observation.confidence for observation in observations if observation.confidence is not None]
    if not confidences:
        return None
    return sum(confidences) / len(confidences)


def review_signals_from_consensus_diagnostics(
    diagnostics: "ConsensusDiagnostics", observations: list["Observation"]
) -> ReviewSignals:
    """Builds `ReviewSignals` from M5's real single-language
    reconstruction diagnostics and the Cue's own supporting
    Observations (already scoped to this Cue by the caller -- e.g. via
    `LanguageLayer.observation_ids`)."""
    return ReviewSignals(
        cue_id=diagnostics.cue_id,
        mean_ocr_confidence=_mean_confidence(observations),
        had_disagreement=diagnostics.had_disagreement,
        missing_language_count=0,
        ambiguous_language_count=0,
    )


def review_signals_from_path_b_diagnostics(diagnostics: "PathBDiagnostics") -> ReviewSignals:
    """Builds `ReviewSignals` from M8's real Path B reconstruction
    diagnostics.

    Only the three "reconstruction was NOT confident" phenomena --
    `source_order_issue`, `timing_collision`, `segmentation_ambiguous`
    -- ever raise Review Priority (mapped onto `had_disagreement`, the
    same "the reconstruction has real, checkable evidence of
    inconsistency" semantics M5's cross-frame disagreement uses).
    `rolling_growth` / `sliding_overlap` / `repetition_collapsed` are
    the CONFIDENTLY-resolved cases -- ROADMAP M8's whole point is that
    content GlyphCue could reliably restore does not need a human to
    re-check it, so they never contribute a component on their own.
    Path B has no OCR-confidence or per-language concept, so
    `mean_ocr_confidence`/`missing_language_count`/
    `ambiguous_language_count` are always the honest "no such signal"
    values -- never a fabricated stand-in."""
    reasons: list[str] = []
    if diagnostics.source_order_issue:
        reasons.append(
            "this Cue's source captions were not in their original file order "
            "(sorted by timing for reconstruction; the original-order mismatch "
            "is preserved as evidence, not silently discarded)"
        )
    if diagnostics.timing_collision:
        reasons.append(
            "a neighboring caption overlaps this one in time with no textual "
            "relationship -- kept separate rather than guessed at"
        )
    if diagnostics.segmentation_ambiguous:
        reasons.append(
            "segmentation ambiguity -- a neighboring caption shares only a "
            "single coincidental character with this one, not enough evidence "
            "to confidently merge or confidently keep separate"
        )

    uncertain = bool(reasons)
    disagreement_detail = (
        ("path_b_reconstruction_uncertain", "Reconstruction could not confidently resolve this Cue: " + "; ".join(reasons) + ".")
        if reasons
        else None
    )
    return ReviewSignals(
        cue_id=diagnostics.cue_id,
        mean_ocr_confidence=None,
        had_disagreement=uncertain,
        missing_language_count=0,
        ambiguous_language_count=0,
        disagreement_detail=disagreement_detail,
    )


def review_signals_from_multilingual_diagnostics(
    diagnostics: "MultilingualDiagnostics", observations: list["Observation"]
) -> ReviewSignals:
    """Builds `ReviewSignals` from M6's real multilingual reconstruction
    diagnostics and the Cue's own supporting Observations across all of
    its language layers."""
    return ReviewSignals(
        cue_id=diagnostics.cue_id,
        mean_ocr_confidence=_mean_confidence(observations),
        had_disagreement=False,
        missing_language_count=len(diagnostics.missing_languages),
        ambiguous_language_count=len(diagnostics.ambiguous_languages),
    )
