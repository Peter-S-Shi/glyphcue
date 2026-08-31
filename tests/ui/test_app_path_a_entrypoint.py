from fractions import Fraction
from pathlib import Path

import av
import numpy as np
from PySide6.QtCore import QEventLoop, QTimer

from glyphcue.adapters.ocr_types import OcrTextRegion
from glyphcue.jobs.job import JobState
from glyphcue.ui import app as app_module
from glyphcue.ui.app import create_path_a_app
from glyphcue.ui.path_a_media_pane import PathAMediaPane
from tests.support.fake_ocr_engine import FakeOcrEngine


def _write_test_video(path: Path) -> None:
    container = av.open(str(path), mode="w")
    stream = container.add_stream("h264", rate=10)
    stream.width = 32
    stream.height = 32
    stream.pix_fmt = "yuv420p"
    stream.codec_context.time_base = Fraction(1, 1000)
    stream.codec_context.gop_size = 1
    for pts_ms in range(0, 200, 100):
        array = np.full((32, 32, 3), 100, dtype=np.uint8)
        frame = av.VideoFrame.from_ndarray(array, format="rgb24").reformat(format="yuv420p")
        frame.pts = pts_ms
        frame.time_base = Fraction(1, 1000)
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()


def _wait_for(job, timeout: float = 5.0) -> None:
    loop = QEventLoop()
    job.finished.connect(loop.quit)
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(int(timeout * 1000))
    loop.exec()
    job.wait(timeout=0.5)


def test_create_path_a_app_returns_a_usable_pane(qapp_guard, tmp_path):
    app, pane = create_path_a_app(db_path=tmp_path / "glyphcue.sqlite3")

    assert isinstance(pane, PathAMediaPane)
    assert app is not None


def test_create_path_a_app_wires_a_real_track_group_repository(qapp_guard, tmp_path):
    db_path = tmp_path / "glyphcue.sqlite3"

    _app, pane = create_path_a_app(db_path=db_path)
    pane.roi_x_spin.setValue(0.1)
    pane.roi_width_spin.setValue(0.5)
    pane.save_roi_button.click()

    _app2, pane2 = create_path_a_app(db_path=db_path)

    assert pane2.current_roi().x == 0.1


def test_create_path_a_app_constructs_the_live_single_language_runtime(
    qapp_guard, tmp_path, monkeypatch
):
    constructed_languages: list[str] = []

    def paddle_factory(language: str = "en") -> FakeOcrEngine:
        constructed_languages.append(language)
        return FakeOcrEngine(
            regions=[OcrTextRegion(text="你好朋友", language=language, confidence=0.9)]
        )

    monkeypatch.setattr(app_module, "PaddleOcrEngine", paddle_factory)
    video_path = tmp_path / "production-pane.mp4"
    _write_test_video(video_path)
    _app, pane = create_path_a_app(db_path=tmp_path / "glyphcue.sqlite3")
    pane.language_selection_panel.set_languages(("zh",))
    pane.open_video(video_path)

    pane.run_ocr_button.click()
    _wait_for(pane.current_ocr_job)

    assert pane.current_ocr_job.state is JobState.SUCCEEDED
    assert constructed_languages == ["zh"]
