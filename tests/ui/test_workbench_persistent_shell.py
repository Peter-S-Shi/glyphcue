from fractions import Fraction
from pathlib import Path

import av
import numpy as np
import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QCloseEvent, QKeySequence
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QSplitter

import glyphcue.ui.app as app_module
from glyphcue.application.review_priority import ReviewPriority
from glyphcue.domain.cue import Cue
from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.domain.review_state import ReviewState
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


def _visible_new_windows(before: set[object]) -> list[QMainWindow]:
    return [
        w
        for w in set(QApplication.topLevelWidgets()) - before
        if isinstance(w, QMainWindow) and w.isVisible()
    ]


def test_create_app_returns_persistent_workbench_as_main_window(qapp_guard, tmp_path):
    # DOG-008: The startup experience is the full persistent Evidence Workbench,
    # not a narrow A/B dialog chooser.
    app, workbench = create_app(db_path=tmp_path / "glyphcue.sqlite3")

    assert isinstance(workbench.window, QMainWindow)
    splitter = workbench.window.findChild(QSplitter)
    assert splitter is not None
    assert splitter.count() == 3

    assert workbench.path_a_mode_button is not None
    assert workbench.path_b_mode_button is not None


def test_only_persistent_workbench_is_visible_after_startup_open_and_switch(
    qapp_guard, tmp_path
):
    before = set(QApplication.topLevelWidgets())
    video_path = tmp_path / "clip.mp4"
    _write_test_video(video_path)
    caption_path = tmp_path / "input.srt"
    caption_path.write_text(_SRT_TEXT, encoding="utf-8")

    _app, workbench = create_app(db_path=tmp_path / "glyphcue.sqlite3")
    workbench.window.show()

    # At startup, only workbench is visible
    vis = _visible_new_windows(before)
    assert len(vis) == 1
    assert vis[0] is workbench.window

    # After opening video in Path A, only workbench is visible (legacy pane.window is NOT shown)
    pane_a = workbench.open_video(video_path)
    vis = _visible_new_windows(before)
    assert len(vis) == 1
    assert vis[0] is workbench.window
    assert pane_a.window is not workbench.window or not hasattr(pane_a, "_standalone_window")
    assert pane_a.window.isVisible() is False or pane_a.window is workbench.window

    # After opening caption file in Path B, only workbench is visible
    workspace_b = workbench.open_caption_file(caption_path)
    vis = _visible_new_windows(before)
    assert len(vis) == 1
    assert vis[0] is workbench.window
    assert workspace_b.window.isVisible() is False or workspace_b.window is workbench.window

    # After switching back to Path A, still only workbench is visible
    workbench.switch_to_mode("path_a")
    vis = _visible_new_windows(before)
    assert len(vis) == 1
    assert vis[0] is workbench.window


def test_closing_workbench_commits_pending_edits_for_active_mode(qapp_guard, tmp_path):
    # DOG-004: Closing the persistent workbench must commit pending edits in active mode
    caption_path = tmp_path / "input.srt"
    caption_path.write_text(_SRT_TEXT, encoding="utf-8")

    _app, workbench = create_app(db_path=tmp_path / "glyphcue.sqlite3")
    workbench.window.show()

    workspace = workbench.open_caption_file(caption_path)
    assert len(workspace.qa.cues) == 1

    # User modifies text in QA language layer without pressing enter/approve
    card = workspace.qa.language_layers_panel.cards[0]
    card.text_edit.setPlainText("Unsaved Close Text")

    # Send close event to the persistent workbench window
    close_event = QCloseEvent()
    QApplication.sendEvent(workbench.window, close_event)

    # Verify pending edits were committed
    assert workspace.qa.cues[0].language_layers[0].text == "Unsaved Close Text"
    assert workspace.qa.cues[0].review_state == ReviewState.NEEDS_REVIEW


def test_qa_shortcuts_are_active_on_persistent_workbench_window(qapp_guard, tmp_path):
    caption_path = tmp_path / "input.srt"
    caption_path.write_text(_SRT_TEXT, encoding="utf-8")

    _app, workbench = create_app(db_path=tmp_path / "glyphcue.sqlite3")
    workbench.window.show()

    workspace = workbench.open_caption_file(caption_path)
    assert len(workspace.qa.cues) == 1
    assert workspace.qa.cues[0].review_state != ReviewState.APPROVED

    # Shortcut execution on workbench window
    workspace.qa.approve_shortcut.activated.emit()
    assert workspace.qa.cues[0].review_state == ReviewState.APPROVED
