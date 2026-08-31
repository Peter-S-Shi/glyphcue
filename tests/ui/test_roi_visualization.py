from glyphcue.domain.roi import ROI
from glyphcue.ui.roi_visualization import RoiVisualization


def test_default_roi_visualization_shows_the_whole_frame(qapp_guard):
    widget = RoiVisualization()

    assert widget.roi == ROI(0.0, 0.0, 1.0, 1.0)


def test_set_roi_updates_the_public_roi_state(qapp_guard):
    widget = RoiVisualization()

    widget.set_roi(ROI(0.1, 0.2, 0.5, 0.3))

    assert widget.roi == ROI(0.1, 0.2, 0.5, 0.3)


def test_paints_without_crashing_at_a_real_size(qapp_guard):
    # A real render pass (not just state) -- catches paintEvent errors
    # that a pure state assertion would miss, while staying safe to run
    # headlessly (plain QWidget, no QVideoWidget native-surface
    # dependency).
    widget = RoiVisualization()
    widget.set_roi(ROI(0.25, 0.25, 0.5, 0.5))
    widget.resize(200, 80)

    widget.repaint()
