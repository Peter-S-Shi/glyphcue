from fractions import Fraction
from pathlib import Path

import av
import numpy as np
import pytest

from glyphcue.adapters.ocr_types import OcrRuntimeInfo, OcrTextRegion
from glyphcue.application.consensus_reconstruction import reconstruct_cues_with_consensus
from glyphcue.application.ocr_evidence_job import STATE_TRIGGER_DETAIL_KEY
from glyphcue.application.ocr_invocation_policy import ChangeTriggeredOcrPolicy
from glyphcue.application.pipeline_metrics import PipelineMetrics
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.application.trigger_replay import run_trigger_replay
from glyphcue.domain.observation import Observation
from glyphcue.domain.provenance import Provenance, ProvenanceKind
from glyphcue.domain.roi import ROI
from tests.support.fake_ocr_engine import FakeOcrEngine


def _make_frame(value: int) -> np.ndarray:
    return np.full((32, 32, 3), value, dtype=np.uint8)


def _make_obs(id_: str, text: str, start: float, end: float | None = None, state_trigger: str | None = None) -> Observation:
    detail = {STATE_TRIGGER_DETAIL_KEY: state_trigger} if state_trigger else {}
    return Observation(
        id=id_,
        text=text,
        start_time=start,
        end_time=end if end is not None else start + 0.001,
        provenance=Provenance(kind=ProvenanceKind.OCR_ENGINE, source="PaddleOCR", detail=detail),
        language="en",
        confidence=0.95,
    )


def test_deferred_onset_ocr_does_not_invoke_ocr_immediately_on_first_diff_crossing():
    policy = ChangeTriggeredOcrPolicy(
        change_threshold=0.02,
        confirmation_threshold=0.02,
        stability_threshold=0.015,
        min_stable_frames=2,
        min_episode_duration=0.066,
        max_gap_seconds=2.0,
    )
    baseline = _make_frame(50)
    assert policy.should_ocr(baseline, 0.0) is True  # first_frame

    # First crossing of change_threshold (value 60: diff=10/255=0.039 > 0.02)
    # MUST NOT immediately trigger OCR!
    frame_onset = _make_frame(60)
    assert policy.should_ocr(frame_onset, 0.033) is False

    assert policy.candidate_transition_episodes == 1
    assert policy.confirmed_transition_episodes == 0
    assert policy.suppressed_candidate_triggers >= 1


def test_fixed_confirmed_baseline_is_held_during_candidate_episode():
    policy = ChangeTriggeredOcrPolicy(
        change_threshold=0.02,
        confirmation_threshold=0.02,
        stability_threshold=0.015,
        min_stable_frames=2,
        min_episode_duration=0.066,
        max_gap_seconds=2.0,
    )
    baseline = _make_frame(50)
    policy.should_ocr(baseline, 0.0)

    # Frame 1: diff=0.039 -> candidate opens, baseline remains 50
    policy.should_ocr(_make_frame(60), 0.033)

    # Frame 2: diff against baseline(50) is 0.027 (value 57).
    # If baseline had shifted to 60, diff would be 3/255=0.011 (below threshold).
    # Because baseline is held fixed at 50, it correctly measures against original 50!
    assert policy._confirmed_ocr_frame[0, 0, 0] == 50


def test_repeated_low_amplitude_motion_does_not_reopen_costly_episodes():
    policy = ChangeTriggeredOcrPolicy(
        change_threshold=0.02,
        confirmation_threshold=0.02,
        stability_threshold=0.015,
        min_stable_frames=2,
        min_episode_duration=0.066,
        max_gap_seconds=2.0,
    )
    baseline = _make_frame(50)
    assert policy.should_ocr(baseline, 0.0) is True  # 1st call

    # Fluctuates around 50 (+/- 6 pixels = 0.023 diff) then returns to 50
    # 56 -> 58 -> 55 -> 51 -> 50
    values = [56, 58, 55, 51, 50, 50]
    ocr_decisions = [policy.should_ocr(_make_frame(v), (i + 1) * 0.033) for i, v in enumerate(values)]

    # NONE of these fluctuating frames should have triggered OCR!
    assert not any(ocr_decisions)
    assert policy.confirmed_transition_episodes == 0


def test_transient_noise_spike_returns_to_fixed_baseline_without_any_ocr():
    policy = ChangeTriggeredOcrPolicy(
        change_threshold=0.02,
        confirmation_threshold=0.02,
        stability_threshold=0.015,
        min_stable_frames=2,
        min_episode_duration=0.066,
        max_gap_seconds=2.0,
    )
    baseline = _make_frame(50)
    assert policy.should_ocr(baseline, 0.0) is True

    # 1-frame spike to 120
    assert policy.should_ocr(_make_frame(120), 0.033) is False
    # Immediately returns to 50
    assert policy.should_ocr(_make_frame(50), 0.066) is False
    assert policy.should_ocr(_make_frame(50), 0.099) is False

    assert policy.confirmed_transition_episodes == 0


def test_genuine_transition_confirms_and_invokes_at_most_one_settled_ocr():
    policy = ChangeTriggeredOcrPolicy(
        change_threshold=0.02,
        confirmation_threshold=0.02,
        stability_threshold=0.015,
        min_stable_frames=1,
        min_episode_duration=0.033,
        max_transition_seconds=0.35,
        max_gap_seconds=2.0,
    )
    shot_a = _make_frame(50)
    assert policy.should_ocr(shot_a, 0.0) is True  # call 1 (first_frame)

    # Multi-frame cut burst from 50 to 200:
    # 0.033s: 80 (diff=0.117 > 0.02) -> candidate onset (suppressed)
    # 0.066s: 120 (diff=0.274) -> burst (suppressed)
    # 0.099s: 160 (diff=0.431) -> burst (suppressed)
    # 0.133s: 200 (shot B arrives) -> burst transition (suppressed)
    # 0.166s: 200 (shot B continues) -> stable! -> SETTLED & CONFIRMED! (call 2)
    assert policy.should_ocr(_make_frame(80), 0.033) is False
    assert policy.should_ocr(_make_frame(120), 0.066) is False
    assert policy.should_ocr(_make_frame(160), 0.099) is False
    assert policy.should_ocr(_make_frame(200), 0.133) is False
    assert policy.should_ocr(_make_frame(200), 0.166) is True  # ONE confirmed OCR call!

    # Further frames of shot B -> no OCR
    assert policy.should_ocr(_make_frame(200), 0.200) is False
    assert policy.should_ocr(_make_frame(200), 0.233) is False

    assert policy.last_trigger_reason == "change_detected"
    assert policy.confirmed_transition_episodes == 1


def test_same_text_continuity_merges_adjacent_identical_reconstructed_cues_across_cut():
    # Observations across a visual editing transition:
    # 1. 10.0s: "don't say it" (pre-cut)
    # 2. 18.4s: "don't say it" (cut onset)
    # 3. 18.57s: "don't say it" (post-cut settled)
    # 4. 19.5s: "don't say it" (periodic confirmation)
    observations = [
        _make_obs("o1", "don't say it", start=10.0, end=18.4, state_trigger="first_frame"),
        _make_obs("o2", "don't say it", start=18.4, end=18.57, state_trigger="change_detected"),
        _make_obs("o3", "don't say it", start=18.57, end=19.5, state_trigger="change_detected"),
        _make_obs("o4", "don't say it", start=19.5, end=19.87, state_trigger="periodic_confirmation"),
    ]

    cues, diagnostics = reconstruct_cues_with_consensus(observations)

    assert len(cues) == 1
    assert cues[0].language_layers[0].text == "don't say it"
    assert cues[0].start_time == 10.0
    assert cues[0].end_time == 19.87
    assert set(cues[0].language_layers[0].observation_ids) == {"o1", "o2", "o3", "o4"}


def _write_test_video(path: Path, frames: list[tuple[int, int]]) -> None:
    container = av.open(str(path), mode="w")
    stream = container.add_stream("h264", rate=1000)
    stream.width = 32
    stream.height = 32
    stream.pix_fmt = "yuv420p"
    stream.codec_context.time_base = Fraction(1, 1000)
    stream.codec_context.gop_size = 1
    stream.codec_context.max_b_frames = 0
    for pts_ms, gray in frames:
        array = np.full((32, 32, 3), gray, dtype=np.uint8)
        frame = av.VideoFrame.from_ndarray(array, format="rgb24").reformat(format="yuv420p")
        frame.pts = pts_ms
        frame.time_base = Fraction(1, 1000)
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()


def test_trigger_replay_produces_identical_decisions_without_calling_ocr_engine(tmp_path):
    video_path = tmp_path / "replay_test.mp4"
    # 0ms: 50, 100ms: 50, 200ms: 200, 300ms: 200, 400ms: 200, 500ms: 50, 600ms: 50
    _write_test_video(
        video_path,
        [(0, 50), (100, 50), (200, 200), (300, 200), (400, 200), (500, 50), (600, 50)],
    )

    policy = ChangeTriggeredOcrPolicy(
        change_threshold=0.05,
        confirmation_threshold=0.05,
        stability_threshold=0.02,
        min_stable_frames=1,
        min_episode_duration=0.05,
    )

    result = run_trigger_replay(
        video_path,
        ProcessingRange(),
        ROI(0.0, 0.0, 1.0, 1.0),
        policy=policy,
    )

    assert result.frames_analyzed == 7
    assert result.decided_ocr_calls == 3  # t=0.0s (first_frame), t=0.3s (200 settled), t=0.6s (50 settled)
    assert result.confirmed_transition_episodes == 2
    assert len(result.decisions) == 3
    assert result.decisions[0].trigger_reason == "first_frame"
    assert result.decisions[1].trigger_reason == "change_detected"
    assert result.decisions[2].trigger_reason == "change_detected"

    report = result.format_report()
    assert "Trigger Replay Report" in report
    assert "Decided OCR Calls:" in report and "3" in report
