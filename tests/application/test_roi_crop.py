import numpy as np

from glyphcue.application.roi_crop import crop_to_roi
from glyphcue.domain.roi import ROI


def test_crop_to_roi_selects_the_fractional_region_of_a_frame():
    frame = np.arange(100 * 200 * 3, dtype=np.uint8).reshape(100, 200, 3)
    roi = ROI(x=0.25, y=0.5, width=0.5, height=0.25)

    cropped = crop_to_roi(frame, roi)

    # x=0.25*200=50 .. (0.25+0.5)*200=150; y=0.5*100=50 .. (0.5+0.25)*100=75
    assert cropped.shape == (25, 100, 3)
    np.testing.assert_array_equal(cropped, frame[50:75, 50:150])


def test_crop_to_roi_covering_the_whole_frame_returns_it_unchanged():
    frame = np.ones((10, 20, 3), dtype=np.uint8)
    roi = ROI(x=0.0, y=0.0, width=1.0, height=1.0)

    cropped = crop_to_roi(frame, roi)

    np.testing.assert_array_equal(cropped, frame)
