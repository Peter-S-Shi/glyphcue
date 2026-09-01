import pytest

from glyphcue.domain.cue import Cue
from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.ui.export_controls import ExportControls


def _cue(id_: str, text: str) -> Cue:
    return Cue(
        id=id_,
        start_time=0.0,
        end_time=1.0,
        language_layers=(LanguageLayer(language="en", text=text),),
    )


def test_the_same_source_can_export_srt_then_switch_to_vtt(qapp_guard, tmp_path):
    # DESIGN.md section 28's required export surface is 4 user-reachable
    # formats -- a generic export that only ever reuses the input
    # suffix cannot offer this (an .srt source could never produce a
    # .vtt). ExportControls' format picker must let the SAME source
    # produce either.
    source = tmp_path / "input.srt"
    controls = ExportControls(
        get_cues=lambda: [_cue("c1", "line one")],
        commit_pending_edits=lambda: None,
        source_path=source,
    )

    controls.format_combo.setCurrentText("SRT")
    srt_destination = controls.export()

    controls.format_combo.setCurrentText("VTT")
    vtt_destination = controls.export()

    assert srt_destination.suffix == ".srt"
    assert vtt_destination.suffix == ".vtt"
    assert srt_destination.exists()
    assert vtt_destination.exists()
    assert "line one" in srt_destination.read_text(encoding="utf-8")
    assert "line one" in vtt_destination.read_text(encoding="utf-8")


def test_a_vtt_source_can_switch_to_export_srt(qapp_guard, tmp_path):
    source = tmp_path / "input.vtt"
    controls = ExportControls(
        get_cues=lambda: [_cue("c1", "line one")],
        commit_pending_edits=lambda: None,
        source_path=source,
    )

    controls.format_combo.setCurrentText("SRT")
    destination = controls.export()

    assert destination.suffix == ".srt"
    assert destination.exists()


def test_export_refuses_when_the_computed_destination_would_equal_the_source(
    qapp_guard, tmp_path, monkeypatch
):
    source = tmp_path / "input.srt"
    controls = ExportControls(
        get_cues=lambda: [_cue("c1", "line one")],
        commit_pending_edits=lambda: None,
        source_path=source,
    )
    monkeypatch.setattr(controls, "_destination", lambda: source)

    with pytest.raises(ValueError):
        controls.export()


def test_export_button_click_refuses_overwrite_without_crashing_and_shows_status(
    qapp_guard, tmp_path, monkeypatch
):
    source = tmp_path / "input.srt"
    source.write_text("original", encoding="utf-8")
    controls = ExportControls(
        get_cues=lambda: [_cue("c1", "line one")],
        commit_pending_edits=lambda: None,
        source_path=source,
        file_dialog_fn=lambda _w, _t, d, _f: (str(source), ""),
    )
    monkeypatch.setattr(controls, "_destination", lambda: source)

    controls.export_button.click()

    assert source.read_text(encoding="utf-8") == "original"
    assert "refus" in controls.status_label.text().lower()


def test_export_button_opens_save_as_dialog_and_writes_to_chosen_path(qapp_guard, tmp_path):
    source = tmp_path / "video.mp4"
    chosen = tmp_path / "custom_folder" / "my_custom_subtitles.srt"
    chosen.parent.mkdir(parents=True, exist_ok=True)

    controls = ExportControls(
        get_cues=lambda: [_cue("c1", "line one")],
        commit_pending_edits=lambda: None,
        source_path=source,
        file_dialog_fn=lambda _w, _t, _d, _f: (str(chosen), "SubRip Subtitle (*.srt)"),
    )

    controls.export_button.click()

    assert chosen.exists()
    assert "line one" in chosen.read_text(encoding="utf-8")
    assert "Exported to" in controls.status_label.text()


def test_export_button_cancelled_dialog_does_not_write_file(qapp_guard, tmp_path):
    source = tmp_path / "video.mp4"
    suggested = tmp_path / "video.reconstructed.srt"

    controls = ExportControls(
        get_cues=lambda: [_cue("c1", "line one")],
        commit_pending_edits=lambda: None,
        source_path=source,
        file_dialog_fn=lambda _w, _t, _d, _f: ("", ""),
    )

    controls.export_button.click()

    assert not suggested.exists()
    assert "cancelled" in controls.status_label.text().lower()

