import pytest

from glyphcue.domain.roi import ROI


def test_roi_holds_fractional_bounds():
    roi = ROI(x=0.1, y=0.2, width=0.3, height=0.4)

    assert (roi.x, roi.y, roi.width, roi.height) == (0.1, 0.2, 0.3, 0.4)


def test_roi_rejects_non_positive_width():
    with pytest.raises(ValueError):
        ROI(x=0.0, y=0.0, width=0.0, height=0.5)


def test_roi_rejects_non_positive_height():
    with pytest.raises(ValueError):
        ROI(x=0.0, y=0.0, width=0.5, height=0.0)


def test_roi_rejects_negative_origin():
    with pytest.raises(ValueError):
        ROI(x=-0.1, y=0.0, width=0.5, height=0.5)


def test_roi_rejects_bounds_extending_past_the_frame():
    with pytest.raises(ValueError):
        ROI(x=0.8, y=0.0, width=0.5, height=0.5)
