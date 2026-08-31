from pathlib import Path

from glyphcue.domain.cue import Cue
from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.persistence.database import connect
from glyphcue.persistence.track_group_repository import TrackGroupRepository
from glyphcue.ui.path_a_media_pane import PathAMediaPane


def _cue(id_: str, text: str) -> Cue:
    return Cue(
        id=id_,
        start_time=0.0,
        end_time=1.0,
        language_layers=(LanguageLayer(language="en", text=text),),
    )


def _pane(tmp_path: Path) -> PathAMediaPane:
    db_path = tmp_path / "glyphcue.sqlite3"
    repository = TrackGroupRepository(connect(db_path))
    return PathAMediaPane(repository, db_path=db_path)


def test_export_controls_are_disabled_until_a_video_is_loaded(qapp_guard, tmp_path):
    pane = _pane(tmp_path)

    assert pane.export_controls.export_button.isEnabled() is False


def test_export_srt_writes_a_reconstructed_srt_file_next_to_the_video(qapp_guard, tmp_path):
    video_path = tmp_path / "clip.mp4"
    video_path.write_bytes(b"not a real video, just needs to exist as a path")
    pane = _pane(tmp_path)
    pane._video_path = video_path
    pane.export_controls.set_source_path(video_path)
    pane.qa.set_cues_and_priorities([_cue("c1", "reconstructed line")], {}, {})

    pane.export_controls.format_combo.setCurrentText("SRT")
    pane.export_controls.export_button.click()

    destination = tmp_path / "clip.reconstructed.srt"
    assert destination.exists()
    assert "reconstructed line" in destination.read_text(encoding="utf-8")


def test_export_readable_transcript_writes_a_transcript_file(qapp_guard, tmp_path):
    video_path = tmp_path / "clip.mp4"
    video_path.write_bytes(b"not a real video, just needs to exist as a path")
    pane = _pane(tmp_path)
    pane._video_path = video_path
    pane.export_controls.set_source_path(video_path)
    pane.qa.set_cues_and_priorities([_cue("c1", "reconstructed line")], {}, {})

    pane.export_controls.format_combo.setCurrentText("Readable Transcript")
    pane.export_controls.export_button.click()

    destination = tmp_path / "clip.transcript.txt"
    assert destination.exists()
    assert "reconstructed line" in destination.read_text(encoding="utf-8")


def test_open_video_wires_the_real_video_path_into_export_controls(qapp_guard, tmp_path):
    import av
    import numpy as np
    from fractions import Fraction

    video_path = tmp_path / "clip.mp4"
    container = av.open(str(video_path), mode="w")
    stream = container.add_stream("h264", rate=10)
    stream.width = 32
    stream.height = 32
    stream.pix_fmt = "yuv420p"
    stream.codec_context.time_base = Fraction(1, 1000)
    stream.codec_context.gop_size = 1
    array = np.full((32, 32, 3), 100, dtype=np.uint8)
    frame = av.VideoFrame.from_ndarray(array, format="rgb24").reformat(format="yuv420p")
    frame.pts = 0
    frame.time_base = Fraction(1, 1000)
    for packet in stream.encode(frame):
        container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()

    pane = _pane(tmp_path)
    pane.open_video(video_path)

    assert pane.export_controls.export_button.isEnabled() is True
