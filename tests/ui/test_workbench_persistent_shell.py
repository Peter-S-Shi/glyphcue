from fractions import Fraction
from pathlib import Path

import av
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QSplitter

import glyphcue.ui.app as app_module
from glyphcue.ui.app import GlyphCueEntry, GlyphCueWorkbench, create_app
from glyphcue.ui.path_a_media_pane import PathAMediaPane
from glyphcue.ui.path_b_workspace import PathBWorkspace

_SRT_TEXT = """1
00:00:00,000 --> 00:00:02,000
Hello there
"""


def _write_test_video(path: Path) -> None:
    container = av.open(str(path), mode="w")
    stream = container.add_stream("h264", rate=10)
    stream.width = 32
    stream.height = 32
    stream.pix_fmt = "yuv420p"
    stream.codec_context.time_base = Fraction(1, 1000)
    stream.codec_context.gop_size = 1
    for pts_ms in range(0, 500, 100):
        array = np.full((32, 32, 3), 100, dtype=np.uint8)
        frame = av.VideoFrame.from_ndarray(array, format="rgb24").reformat(format="yuv420p")
        frame.pts = pts_ms
        frame.time_base = Fraction(1, 1000)
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()


def test_create_app_returns_persistent_workbench_as_main_window(qapp_guard, tmp_path):
    # DOG-008: The startup experience is the full persistent Evidence Workbench,
    # not a narrow A/B dialog chooser.
    app, workbench = create_app(db_path=tmp_path / "glyphcue.sqlite3")

    assert isinstance(workbench.window, QMainWindow)
    # The workbench shell possesses the 3-pane structure from the start
    splitter = workbench.window.findChild(QSplitter)
    assert splitter is not None
    assert splitter.count() == 3

    # Mode switchers are available in the top chrome
    assert workbench.path_a_mode_button is not None
    assert workbench.path_b_mode_button is not None


def test_mode_switching_occurs_inside_single_persistent_window(qapp_guard, tmp_path):
    video_path = tmp_path / "clip.mp4"
    _write_test_video(video_path)
    caption_path = tmp_path / "input.srt"
    caption_path.write_text(_SRT_TEXT, encoding="utf-8")

    _app, workbench = create_app(db_path=tmp_path / "glyphcue.sqlite3")
    main_window = workbench.window
    main_window.show()

    # Open video in Path A
    pane_a = workbench.open_video(video_path)
    assert workbench.current_mode == "path_a"
    assert workbench.window is main_window
    assert main_window.isVisible() is True

    # Switch mode to Path B
    workspace_b = workbench.open_caption_file(caption_path)
    assert workbench.current_mode == "path_b"
    # Window instance remains the same (no separate window opened/hidden)
    assert workbench.window is main_window

    # Switch back to Path A
    workbench.switch_to_mode("path_a")
    assert workbench.current_mode == "path_a"
    assert workbench.window is main_window
