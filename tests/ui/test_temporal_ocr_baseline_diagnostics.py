import json
import uuid
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

import av
import numpy as np
import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QDialog, QFileDialog, QLabel, QPushButton, QTextEdit

from glyphcue.application.ocr_evidence_job import build_ocr_evidence_job
from glyphcue.application.ocr_invocation_policy import ChangeTriggeredOcrPolicy
from glyphcue.application.pipeline_metrics import OcrInvocationRecord, PipelineMetrics
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.domain.roi import ROI
from glyphcue.ui.app import create_app
from tests.support.fake_ocr_engine import FakeOcrEngine


def test_pipeline_metrics_records_and_aggregates_invocation_diagnostics():
    metrics = PipelineMetrics()
    metrics.frames_analyzed = 100
    metrics.media_seconds_processed = 10.0
    metrics.elapsed_seconds = 5.0
    metrics.engine_initialization_seconds = 0.42

    metrics.record_invocation(
        timestamp=0.0,
        trigger_reason="first_frame",
        difference_score=None,
        dimensions=(100, 40),
        latency_seconds=0.050,
    )
    metrics.record_invocation(
        timestamp=1.0,
        trigger_reason="change_detected",
        difference_score=0.085,
        dimensions=(100, 40),
        latency_seconds=0.030,
    )
    metrics.record_invocation(
        timestamp=3.0,
        trigger_reason="periodic_confirmation",
        difference_score=0.005,
        dimensions=(100, 40),
        latency_seconds=0.070,
    )

    assert metrics.ocr_calls == 3
    assert metrics.engine_initialization_seconds == 0.42
    assert metrics.trigger_counts == {
        "first_frame": 1,
        "change_detected": 1,
        "periodic_confirmation": 1,
    }
    assert pytest.approx(metrics.latency_mean_seconds, rel=1e-3) == 0.050
    assert pytest.approx(metrics.latency_median_seconds, rel=1e-3) == 0.050
    assert pytest.approx(metrics.latency_p95_seconds, rel=1e-3) == 0.068
    assert pytest.approx(metrics.ocr_calls_per_media_minute, rel=1e-3) == 18.0
    assert pytest.approx(metrics.effective_processing_speed, rel=1e-3) == 2.0
    assert pytest.approx(metrics.wall_media_ratio, rel=1e-3) == 0.5
    assert pytest.approx(metrics.slowdown_factor, rel=1e-3) == 0.5

    diag_dict = metrics.to_dict(include_invocations=True)
    assert diag_dict["summary"]["frames_analyzed"] == 100
    assert diag_dict["summary"]["ocr_calls"] == 3
    assert diag_dict["summary"]["engine_initialization_seconds"] == 0.42
    assert diag_dict["summary"]["effective_processing_speed"] == 2.0
    assert diag_dict["summary"]["wall_media_ratio"] == 0.5
    assert diag_dict["summary"]["slowdown_factor"] == 0.5
    assert "realtime_ratio" not in diag_dict["summary"]

    assert len(diag_dict["invocations"]) == 3
    assert diag_dict["invocations"][1]["trigger_reason"] == "change_detected"
    assert diag_dict["invocations"][1]["difference_score"] == 0.085
    assert diag_dict["invocations"][1]["dimensions"] == [100, 40]

    report = metrics.format_summary_report()
    assert "Temporal OCR Baseline Diagnostic Report" in report
    assert "Frames Analyzed:" in report and "100" in report
    assert "OCR Calls:" in report and "3" in report


def test_slow_run_speed_and_wall_media_slowdown_ratio():
    metrics = PipelineMetrics()
    metrics.frames_analyzed = 1000
    metrics.media_seconds_processed = 10.0
    metrics.elapsed_seconds = 200.0

    assert pytest.approx(metrics.effective_processing_speed, rel=1e-3) == 0.05
    assert pytest.approx(metrics.wall_media_ratio, rel=1e-3) == 20.0
    assert pytest.approx(metrics.slowdown_factor, rel=1e-3) == 20.0

    report = metrics.format_summary_report()
    assert "20.00x slower than realtime" in report
    assert "0.05x realtime" in report


def test_change_triggered_policy_exposes_difference_score():
    policy = ChangeTriggeredOcrPolicy(change_threshold=0.05, max_gap_seconds=2.0)
    frame1 = np.zeros((40, 100, 3), dtype=np.uint8)
    frame2 = np.ones((40, 100, 3), dtype=np.uint8) * 200

    assert policy.should_ocr(frame1, 0.0) is True
    assert policy.last_trigger_reason == "first_frame"
    assert policy.last_difference_score is None

    assert policy.should_ocr(frame2, 0.1) is True
    assert policy.last_trigger_reason == "change_detected"
    assert policy.last_difference_score is not None
    assert policy.last_difference_score > 0.05


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


def test_ocr_job_records_invocation_metadata_faithfully(qapp_guard, tmp_path):
    video_path = tmp_path / "test.mp4"
    _write_test_video(video_path, [(0, 0), (100, 0), (500, 200)])
    db_path = tmp_path / "ocr.sqlite3"
    engine = FakeOcrEngine(regions=[])
    metrics = PipelineMetrics()
    run_id = str(uuid.uuid4())

    job = build_ocr_evidence_job(
        video_path,
        ProcessingRange(),
        ROI(0.0, 0.0, 1.0, 1.0),
        engine,
        db_path,
        metrics,
        run_id,
    )

    loop = QEventLoop()
    job.finished.connect(loop.quit)
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(5000)
    job.start()
    loop.exec()
    job.wait(timeout=1.0)

    assert metrics.frames_analyzed == 3
    assert metrics.ocr_calls == 2
    assert len(metrics.invocation_records) == 2
    assert metrics.engine_initialization_seconds >= 0.0

    r1 = metrics.invocation_records[0]
    assert r1.trigger_reason == "first_frame"
    assert r1.difference_score is None
    assert r1.dimensions == (32, 32)
    assert r1.latency_seconds >= 0.0

    r2 = metrics.invocation_records[1]
    assert r2.trigger_reason == "change_detected"
    assert r2.difference_score is not None
    assert r2.difference_score > 0.0


def test_path_a_ui_exposes_diagnostics_report_and_save_actions(qapp_guard, tmp_path):
    app, workbench = create_app(db_path=tmp_path / "glyphcue.sqlite3")
    pane = workbench.path_a_pane
    assert pane is not None

    # Performance diagnostics controls exist inside ocrActionBox
    assert hasattr(pane, "view_diagnostic_report_button")
    assert hasattr(pane, "save_diagnostic_json_button")
    assert hasattr(pane, "copy_diagnostic_summary_button")
    assert hasattr(pane, "diagnostics_summary_label")

    # Populate mock metrics into pane
    metrics = pane.ocr_metrics
    metrics.frames_analyzed = 50
    metrics.media_seconds_processed = 5.0
    metrics.elapsed_seconds = 2.5
    metrics.record_invocation(
        timestamp=0.0,
        trigger_reason="first_frame",
        difference_score=None,
        dimensions=(100, 40),
        latency_seconds=0.045,
    )
    pane._update_diagnostics_ui()

    assert "Calls: 1" in pane.diagnostics_summary_label.text()
    assert pane.view_diagnostic_report_button.isEnabled()
    assert pane.save_diagnostic_json_button.isEnabled()

    # Test View Report Dialog
    with patch.object(QDialog, "exec", return_value=QDialog.DialogCode.Accepted) as mock_dialog_exec:
        pane.view_diagnostic_report_button.click()
        assert mock_dialog_exec.called

    # Test Save JSON Cancel behavior (writes nothing)
    target_json = tmp_path / "diag.json"
    with patch.object(QFileDialog, "getSaveFileName", return_value=("", "")):
        pane.save_diagnostic_json_button.click()
        assert not target_json.exists()

    # Test Save JSON Success behavior
    with patch.object(QFileDialog, "getSaveFileName", return_value=(str(target_json), "JSON Files (*.json)")):
        pane.save_diagnostic_json_button.click()
        assert target_json.exists()
        saved_data = json.loads(target_json.read_text(encoding="utf-8"))
        assert saved_data["summary"]["ocr_calls"] == 1
        assert saved_data["summary"]["effective_processing_speed"] == 2.0
        assert saved_data["summary"]["wall_media_ratio"] == 0.5
        assert len(saved_data["invocations"]) == 1

    # Test Copy Summary behavior
    pane.copy_diagnostic_summary_button.click()
    clipboard_text = QGuiApplication.clipboard().text()
    assert "Temporal OCR Baseline Diagnostic Report" in clipboard_text
