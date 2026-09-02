import av
import numpy as np
import pytest
from fractions import Fraction
from pathlib import Path
from PySide6.QtMultimedia import QMediaPlayer

from glyphcue.domain.roi import ROI
from glyphcue.domain.track_group import TrackGroup
from glyphcue.persistence.track_group_repository import TrackGroupRepository
from glyphcue.ui.path_a_media_pane import PathAMediaPane
from glyphcue.ui.playback_controller import PlaybackController


def _write_test_video(path: Path) -> None:
    container = av.open(str(path), mode="w")
    stream = container.add_stream("h264", rate=10)
    stream.width = 32
    stream.height = 32
    stream.pix_fmt = "yuv420p"
    stream.codec_context.time_base = Fraction(1, 1000)
    stream.codec_context.gop_size = 1
    for pts_ms in range(0, 1000, 100):
        array = np.full((32, 32, 3), 100, dtype=np.uint8)
        frame = av.VideoFrame.from_ndarray(array, format="rgb24").reformat(format="yuv420p")
        frame.pts = pts_ms
        frame.time_base = Fraction(1, 1000)
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()


@pytest.fixture
def repository(tmp_path) -> TrackGroupRepository:
    from glyphcue.persistence.database import connect
    conn = connect(tmp_path / "test.sqlite3")
    repo = TrackGroupRepository(conn)
    repo.save(TrackGroup(id="tg:default", roi=ROI(0.0, 0.0, 1.0, 1.0), languages=["en"]))
    return repo


@pytest.fixture
def test_video(tmp_path) -> Path:
    p = tmp_path / "test_loop.mp4"
    _write_test_video(p)
    return p


def test_playback_controller_ab_loop_state_and_looping_behavior():
    controller = PlaybackController()
    assert controller.is_loop_enabled is False
    assert controller.loop_range is None

    # Invalid range: end <= start rejects
    assert controller.set_ab_loop(2.0, 1.0) is False
    assert controller.set_ab_loop(1.0, 1.0) is False
    assert controller.is_loop_enabled is False

    # Valid range
    assert controller.set_ab_loop(0.2, 0.6, enabled=True) is True
    assert controller.is_loop_enabled is True
    assert controller.loop_range == (0.2, 0.6)

    # Disabling / clearing loop
    controller.clear_ab_loop()
    assert controller.is_loop_enabled is False
    assert controller.loop_range is None


def test_preview_loop_controls_in_path_a_media_pane(qapp_guard, repository, test_video):
    pane = PathAMediaPane(repository)

    assert hasattr(pane, "preview_loop_checkbox")
    assert hasattr(pane, "loop_a_spin")
    assert hasattr(pane, "loop_b_spin")
    assert hasattr(pane, "set_loop_a_from_playhead_button")
    assert hasattr(pane, "set_loop_b_from_playhead_button")
    assert hasattr(pane, "play_loop_button")
    assert hasattr(pane, "clear_loop_button")
    assert hasattr(pane, "preview_loop_status_label")

    assert pane.preview_loop_checkbox.isChecked() is False
    assert "Off" in pane.preview_loop_status_label.text()

    pane.open_video(test_video)

    pane.loop_a_spin.setValue(0.15)
    pane.loop_b_spin.setValue(0.45)
    pane.preview_loop_checkbox.setChecked(True)

    assert pane.controller.is_loop_enabled is True
    assert pane.controller.loop_range == (0.15, 0.45)
    assert "0.15" in pane.preview_loop_status_label.text()
    assert "0.45" in pane.preview_loop_status_label.text()
    assert "Preview only" in pane.preview_loop_status_label.text()

    # Critical separation: Preview loop MUST NOT alter OCR Processing Range!
    processing_range = pane.current_processing_range()
    assert processing_range.is_whole_media() is True
    assert "Whole media" in pane.ocr_range_summary_label.text()

    pane.clear_loop_button.click()
    assert pane.preview_loop_checkbox.isChecked() is False
    assert pane.controller.is_loop_enabled is False
    assert "Off" in pane.preview_loop_status_label.text()


def test_set_processing_range_from_playhead_actions(qapp_guard, repository, test_video):
    pane = PathAMediaPane(repository)

    assert hasattr(pane, "set_range_start_from_playhead_button")
    assert hasattr(pane, "set_range_end_from_playhead_button")

    pane.open_video(test_video)

    pane.controller.seek(0.35)
    pane.set_range_start_from_playhead_button.click()

    assert pane.limit_processing_range_checkbox.isChecked() is True
    assert pane.processing_range_start_spin.value() == pytest.approx(0.35, abs=0.01)

    pane.controller.seek(0.85)
    pane.set_range_end_from_playhead_button.click()

    assert pane.limit_processing_range_checkbox.isChecked() is True
    assert pane.processing_range_end_spin.value() == pytest.approx(0.85, abs=0.01)

    assert "0.35s" in pane.ocr_range_summary_label.text()
    assert "0.85s" in pane.ocr_range_summary_label.text()

    assert pane.controller.is_loop_enabled is False


def test_preview_loop_invalid_range_handling(qapp_guard, repository, test_video):
    pane = PathAMediaPane(repository)
    pane.open_video(test_video)

    pane.loop_a_spin.setValue(0.50)
    pane.loop_b_spin.setValue(0.20)
    pane.preview_loop_checkbox.setChecked(True)

    assert pane.controller.is_loop_enabled is False
    assert ("Invalid" in pane.preview_loop_status_label.text() or "must be >" in pane.preview_loop_status_label.text())


def test_preview_loop_clears_on_video_switching(qapp_guard, repository, test_video, tmp_path):
    pane = PathAMediaPane(repository)
    pane.open_video(test_video)

    pane.loop_a_spin.setValue(0.1)
    pane.loop_b_spin.setValue(0.3)
    pane.preview_loop_checkbox.setChecked(True)
    assert pane.controller.is_loop_enabled is True

    video2 = tmp_path / "video2.mp4"
    _write_test_video(video2)
    pane.open_video(video2)

    assert pane.controller.is_loop_enabled is False


def test_preview_loop_play_loop_button_action(qapp_guard, repository, test_video):
    pane = PathAMediaPane(repository)
    pane.open_video(test_video)

    pane.loop_a_spin.setValue(0.2)
    pane.loop_b_spin.setValue(0.7)

    # Clicking Play Loop automatically enables loop, seeks to A, and starts playing
    pane.play_loop_button.click()

    assert pane.preview_loop_checkbox.isChecked() is True
    assert pane.controller.is_loop_enabled is True
    assert pane.controller.position_seconds == pytest.approx(0.2, abs=0.05)


def test_preview_loop_and_range_actions_without_video(qapp_guard, repository):
    pane = PathAMediaPane(repository)

    # Without video, clicking playhead copy buttons safely defaults to 0.0 without throwing
    pane.set_range_start_from_playhead_button.click()
    assert pane.limit_processing_range_checkbox.isChecked() is True
    assert pane.processing_range_start_spin.value() == 0.0

    pane.set_range_end_from_playhead_button.click()
    assert pane.processing_range_end_spin.value() == 0.0

    # Setting loop without video
    pane.loop_a_spin.setValue(1.0)
    pane.loop_b_spin.setValue(2.0)
    pane.preview_loop_checkbox.setChecked(True)
    assert pane.controller.is_loop_enabled is True
    pane.clear_loop_button.click()
    assert pane.controller.is_loop_enabled is False


def test_path_switching_preserves_preview_loop_isolation(qapp_guard, repository, test_video, tmp_path):
    switched_paths = []

    def on_caption_file(p: Path) -> None:
        switched_paths.append(p)

    pane = PathAMediaPane(repository, on_open_caption_file=on_caption_file)
    pane.open_video(test_video)

    pane.loop_a_spin.setValue(0.1)
    pane.loop_b_spin.setValue(0.4)
    pane.preview_loop_checkbox.setChecked(True)

    dummy_srt = tmp_path / "subtitles.srt"
    dummy_srt.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")

    pane.switch_to_caption_file(dummy_srt)
    assert switched_paths == [dummy_srt]
    # Preview loop state is isolated and does not corrupt processing range
    assert pane.current_processing_range().is_whole_media() is True


def test_cue_replay_suspends_and_restores_ab_loop(qapp_guard, repository, test_video):
    pane = PathAMediaPane(repository)
    pane.open_video(test_video)

    # Set and enable A-B loop: 0.1s to 0.3s
    pane.loop_a_spin.setValue(0.1)
    pane.loop_b_spin.setValue(0.3)
    pane.preview_loop_checkbox.setChecked(True)
    assert pane.controller.is_loop_enabled is True
    assert pane.controller.loop_range == (0.1, 0.3)

    # Trigger Cue Replay for a cue spanning 0.4s to 0.8s
    from glyphcue.domain.cue import Cue
    from glyphcue.domain.language_layer import LanguageLayer

    cue = Cue(
        id="cue-1",
        start_time=0.4,
        end_time=0.8,
        language_layers=[LanguageLayer(language="en", text="Test Cue")],
    )

    pane._on_replay(cue)
    # A-B loop must be temporarily suspended during span replay
    assert pane.controller.is_loop_enabled is False

    # Simulate position reaching end of span (800ms)
    pane.controller._on_position_changed_during_span(850)

    # Span replay pauses and restores original A-B loop state
    assert pane.controller.is_loop_enabled is True
    assert pane.controller.loop_range == (0.1, 0.3)
