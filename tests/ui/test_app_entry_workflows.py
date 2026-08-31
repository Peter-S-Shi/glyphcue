from fractions import Fraction
from pathlib import Path

import av
import numpy as np

from glyphcue.ui.app import GlyphCueEntry, create_app
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


def test_create_app_returns_the_empty_state_entry_not_a_workflow_pane(qapp_guard, tmp_path):
    app, entry = create_app(db_path=tmp_path / "glyphcue.sqlite3")

    assert isinstance(entry, GlyphCueEntry)
    assert app is not None
    assert entry.open_video_button is not None
    assert entry.open_caption_button is not None


def test_open_video_transitions_to_a_real_path_a_pane(qapp_guard, tmp_path):
    video_path = tmp_path / "clip.mp4"
    _write_test_video(video_path)
    _app, entry = create_app(db_path=tmp_path / "glyphcue.sqlite3")

    pane = entry.open_video(video_path)

    assert isinstance(pane, PathAMediaPane)
    assert "32x32" in pane.metadata_label.text()


def test_open_caption_file_transitions_to_a_real_path_b_workspace(qapp_guard, tmp_path):
    source = tmp_path / "input.srt"
    source.write_text(_SRT_TEXT, encoding="utf-8")
    _app, entry = create_app(db_path=tmp_path / "glyphcue.sqlite3")

    workspace = entry.open_caption_file(source)

    assert isinstance(workspace, PathBWorkspace)
    assert workspace.queue.count() == 1


def test_open_caption_file_never_writes_to_the_source_srt(qapp_guard, tmp_path):
    source = tmp_path / "input.srt"
    source.write_text(_SRT_TEXT, encoding="utf-8")
    _app, entry = create_app(db_path=tmp_path / "glyphcue.sqlite3")

    entry.open_caption_file(source)

    assert source.read_text(encoding="utf-8") == _SRT_TEXT


def test_open_caption_file_with_a_recoverable_bad_event_surfaces_an_import_warning(
    qapp_guard, tmp_path
):
    source = tmp_path / "input.srt"
    source.write_text(
        """1
00:00:00,000 --> 00:00:02,000
Good line one

2
00:00:03,000 --> 00:00:02,500
Bad inverted line

3
00:00:04,000 --> 00:00:06,000
Good line two
""",
        encoding="utf-8",
    )
    _app, entry = create_app(db_path=tmp_path / "glyphcue.sqlite3")

    workspace = entry.open_caption_file(source)

    assert workspace.queue.count() == 2
    assert "1" in workspace.import_warnings_label.text()
