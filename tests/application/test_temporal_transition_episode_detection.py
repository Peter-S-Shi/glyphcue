import numpy as np
import pytest

from glyphcue.application.consensus_reconstruction import reconstruct_cues_with_consensus
from glyphcue.application.ocr_evidence_job import STATE_TRIGGER_DETAIL_KEY
from glyphcue.application.ocr_invocation_policy import ChangeTriggeredOcrPolicy
from glyphcue.application.pipeline_metrics import PipelineMetrics
from glyphcue.domain.observation import Observation
from glyphcue.domain.provenance import Provenance, ProvenanceKind


def _make_frame(value: int) -> np.ndarray:
    return np.full((32, 32, 3), value, dtype=np.uint8)


def _make_obs(id_: str, text: str, start: float, state_trigger: str | None = None) -> Observation:
    detail = {STATE_TRIGGER_DETAIL_KEY: state_trigger} if state_trigger else {}
    return Observation(
        id=id_,
        text=text,
        start_time=start,
        end_time=start + 0.001,
        provenance=Provenance(kind=ProvenanceKind.OCR_ENGINE, source="PaddleOCR", detail=detail),
        language="en",
        confidence=0.95,
    )


def test_low_level_background_motion_below_threshold_does_not_trigger_ocr():
    policy = ChangeTriggeredOcrPolicy(change_threshold=0.05, max_gap_seconds=2.0)
    baseline = _make_frame(100)
    assert policy.should_ocr(baseline, 0.0) is True  # first_frame

    # Low-level noise/drift (e.g. pixel diff 0.01-0.03 < 0.05)
    for i in range(1, 10):
        t = i * 0.033
        noise_frame = _make_frame(100 + (i % 3))
        assert policy.should_ocr(noise_frame, t) is False

    assert policy.transition_episodes == 0
    assert policy.suppressed_candidate_triggers == 0


def test_multi_frame_transition_burst_collapses_into_one_episode():
    policy = ChangeTriggeredOcrPolicy(
        change_threshold=0.05,
        confirmation_threshold=0.05,
        stability_threshold=0.02,
        min_stable_frames=1,
        min_episode_duration=0.033,
        max_transition_seconds=0.4,
        max_gap_seconds=2.0,
    )
    shot_a = _make_frame(50)
    assert policy.should_ocr(shot_a, 0.0) is True  # 1st call (first_frame)

    # Frame 1 at 0.033s starts candidate onset -> deferred/suppressed!
    assert policy.should_ocr(_make_frame(70), 0.033) is False

    # Multi-frame cross-dissolve/cut burst across frames 2-5: suppressed!
    burst_values = [90, 110, 140, 170]
    for idx, val in enumerate(burst_values, start=2):
        t = idx * 0.033
        assert policy.should_ocr(_make_frame(val), t) is False

    # Shot B arrives at 200: frame 6 at 0.200s is transition-to-200 (suppressed), frame 7 at 0.233s is stable at 200 (settled & confirmed!)
    shot_b = _make_frame(200)
    assert policy.should_ocr(shot_b, 0.200) is False  # arriving frame of shot B
    assert policy.should_ocr(shot_b, 0.233) is True   # settled! 2nd call (post-cut state)

    # Subsequent identical frames of shot B -> no further OCR
    assert policy.should_ocr(shot_b, 0.266) is False
    assert policy.should_ocr(shot_b, 0.300) is False

    assert policy.last_trigger_reason == "change_detected"
    assert policy.transition_episodes == 1
    assert policy.suppressed_candidate_triggers >= 5


def test_genuine_subtitle_change_triggers_one_ocr_call_and_settles():
    policy = ChangeTriggeredOcrPolicy(
        change_threshold=0.05,
        confirmation_threshold=0.05,
        stability_threshold=0.02,
        min_stable_frames=1,
        min_episode_duration=0.033,
        max_gap_seconds=2.0,
    )
    sub_1 = _make_frame(0)
    assert policy.should_ocr(sub_1, 0.0) is True  # call 1

    # Subtitle changes at t=1.0s to sub_2: candidate onset (suppressed)
    sub_2 = _make_frame(100)
    assert policy.should_ocr(sub_2, 1.000) is False
    # Next frame at 1.033s is stable at sub_2 -> settled & confirmed! (call 2)
    assert policy.should_ocr(sub_2, 1.033) is True
    assert policy.last_trigger_reason == "change_detected"

    # Subsequent identical frames of sub_2 -> no further OCR
    assert policy.should_ocr(sub_2, 1.066) is False
    assert policy.should_ocr(sub_2, 1.100) is False
    assert policy.should_ocr(sub_2, 1.133) is False


def test_max_transition_duration_forces_settle_during_extended_motion():
    policy = ChangeTriggeredOcrPolicy(
        change_threshold=0.05,
        confirmation_threshold=0.05,
        stability_threshold=0.02,
        min_stable_frames=1,
        min_episode_duration=0.033,
        max_transition_seconds=0.2,
        max_gap_seconds=2.0,
    )
    baseline = _make_frame(0)
    assert policy.should_ocr(baseline, 0.0) is True  # first frame

    # Continuous motion changing every frame by 15: suppressed while transition elapsed < 0.2s
    for i in range(1, 6):
        t = i * 0.033  # up to 0.165s
        assert policy.should_ocr(_make_frame(i * 15), t) is False

    # At t=0.250s (elapsed 0.217s >= max_transition_seconds 0.2s), forces settle and OCR
    assert policy.should_ocr(_make_frame(7 * 15), 0.250) is True
    assert policy.last_trigger_reason == "change_detected"
    assert policy.transition_episodes == 1


def test_identical_subtitle_text_persisting_across_visual_transition_remains_one_continuous_cue():
    # Observations:
    # 1. 10.0s: "don't say it" (first_frame)
    # 2. 18.4s: "don't say it" (change_detected across visual cut)
    # 3. 18.57s: "don't say it" (change_detected post-cut settled)
    # 4. 19.5s: "don't say it" (periodic_confirmation)
    observations = [
        _make_obs("o1", "don't say it", start=10.0, state_trigger="first_frame"),
        _make_obs("o2", "don't say it", start=18.4, state_trigger="change_detected"),
        _make_obs("o3", "don't say it", start=18.57, state_trigger="change_detected"),
        _make_obs("o4", "don't say it", start=19.5, state_trigger="periodic_confirmation"),
    ]

    cues, diagnostics = reconstruct_cues_with_consensus(observations)

    # Must remain ONE continuous Cue spanning 10.0s to 19.5s+
    assert len(cues) == 1
    assert cues[0].language_layers[0].text == "don't say it"
    assert cues[0].language_layers[0].observation_ids == ("o1", "o2", "o3", "o4")
    assert cues[0].start_time == 10.0


def test_pipeline_metrics_includes_transition_episodes_and_suppressed_triggers():
    metrics = PipelineMetrics()
    metrics.frames_analyzed = 300
    metrics.ocr_calls = 12
    metrics.media_seconds_processed = 10.0
    metrics.elapsed_seconds = 30.0
    metrics.candidate_transition_episodes = 10
    metrics.confirmed_transition_episodes = 6
    metrics.transition_episodes = 6
    metrics.suppressed_candidate_triggers = 68

    diag = metrics.to_dict()
    assert diag["summary"]["candidate_transition_episodes"] == 10
    assert diag["summary"]["confirmed_transition_episodes"] == 6
    assert diag["summary"]["transition_episodes"] == 6
    assert diag["summary"]["suppressed_candidate_triggers"] == 68

    report = metrics.format_summary_report()
    assert "Candidate Episodes:" in report and "10" in report
    assert "Confirmed Episodes:" in report and "6" in report
    assert "Suppressed Triggers:" in report and "68" in report
