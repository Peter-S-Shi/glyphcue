from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QApplication

import glyphcue.ui.app as app_module


def test_main_launches_the_path_a_workflow_not_the_placeholder_shell(
    qapp_guard, tmp_path, monkeypatch
):
    # main() is production startup composition, not just an alternate
    # factory: it must actually show the M2 Path A workflow window, not
    # the plain M0 placeholder shell.
    #
    # QApplication.exec() is the one genuinely blocking boundary (the OS
    # event loop) and is patched out so the test doesn't hang. Widgets
    # are captured from *inside* the fake exec() call, while main()'s
    # local `window`/`pane` reference is still alive on the stack --
    # once main() returns with exec() stubbed to a no-op, nothing keeps
    # that reference alive and the widget can be garbage-collected
    # immediately, unlike real production where exec() blocks for the
    # whole app lifetime.
    captured_widgets: list[object] = []

    def fake_exec(self) -> int:
        captured_widgets.extend(QApplication.topLevelWidgets())
        return 0

    monkeypatch.setattr(QApplication, "exec", fake_exec)

    before = set(QApplication.topLevelWidgets())
    exit_code = app_module.main(db_path=tmp_path / "glyphcue.sqlite3")

    assert exit_code == 0
    new_windows = set(captured_widgets) - before
    assert len(new_windows) == 1
    (window,) = new_windows
    assert window.findChild(QVideoWidget) is not None
