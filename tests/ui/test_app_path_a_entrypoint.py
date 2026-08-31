from glyphcue.ui.app import create_path_a_app
from glyphcue.ui.path_a_media_pane import PathAMediaPane


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
