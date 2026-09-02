"""M11 Targeted Regression -- narrow-window layout seams.

Seam under test: the real, shown `GlyphCueWorkbench` at concrete window
sizes -- specifically whether a control this round added to the OCR
Evidence Pipeline row is actually reachable, or is pushed outside a pane
whose scroll areas deliberately have horizontal scrolling switched off
(`ScrollBarAlwaysOff`, pinned by
`tests/ui/test_preview_ab_loop_and_playhead_range_actions.py`). With no
horizontal scrollbar, content wider than the viewport is not scrolled to
-- it is simply gone.

`visibleRegion().isEmpty()` is the assertion that matters here: a widget
can report `isVisible()` True, a real size, and a sane geometry while
being entirely outside its scroll viewport.
"""

import pytest
from PySide6.QtWidgets import QSplitter

from glyphcue.ui.app import create_app


def _shown_workbench(qapp_guard, tmp_path, width: int, height: int):
    _app, workbench = create_app(db_path=tmp_path / "glyphcue.sqlite3")
    workbench.resize(width, height)
    workbench.show()
    for _ in range(5):
        qapp_guard.processEvents()
    return workbench


def _ocr_pipeline_controls(pane):
    return {
        "Run OCR": pane.run_ocr_button,
        "Dry Run": pane.dry_run_policy_button,
        "Cancel": pane.cancel_ocr_button,
        "Discard Latest Run": pane.discard_latest_run_button,
    }


def test_every_ocr_pipeline_control_is_reachable_at_the_default_window_size(
    qapp_guard, tmp_path
):
    """1280x720 is the size `GlyphCueWorkbench` opens at."""
    workbench = _shown_workbench(qapp_guard, tmp_path, 1280, 720)

    hidden = [
        name
        for name, button in _ocr_pipeline_controls(workbench.path_a_pane).items()
        if button.visibleRegion().isEmpty()
    ]

    assert hidden == []


def test_the_ocr_pipeline_row_fits_the_center_pane_it_is_guaranteed(qapp_guard, tmp_path):
    """The row's own minimum width has to fit inside the center pane's
    guaranteed minimum width -- otherwise the overflow is silent."""
    workbench = _shown_workbench(qapp_guard, tmp_path, 1280, 720)
    splitter = workbench.findChild(QSplitter)
    center_width = splitter.sizes()[1]
    ocr_box = workbench.path_a_pane.run_ocr_button.parentWidget()

    assert ocr_box.minimumSizeHint().width() <= center_width


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Recorded M11 Targeted Regression finding, deliberately NOT fixed in "
        "this pass: at the workbench's own 1024x600 minimum size the Path A "
        "center and left pane content still overflow their (horizontally "
        "unscrollable) viewports. This is wider than the OCR pipeline row -- "
        "previewLoopBox alone needs ~938px against a ~392px viewport -- and "
        "predates this round's corrective hardening, so fixing it is a "
        "responsive-layout pass, not a targeted regression fix."
    ),
)
def test_the_roi_hint_and_ocr_controls_survive_the_minimum_window_size(qapp_guard, tmp_path):
    workbench = _shown_workbench(qapp_guard, tmp_path, 1024, 600)
    pane = workbench.path_a_pane

    hidden = [
        name
        for name, button in _ocr_pipeline_controls(pane).items()
        if button.visibleRegion().isEmpty()
    ]

    assert hidden == []
    assert pane.roi_hint_label.visibleRegion().isEmpty() is False
