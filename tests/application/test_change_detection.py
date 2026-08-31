import numpy as np

from glyphcue.application.change_detection import frame_difference_score


def test_identical_frames_score_zero():
    frame = np.full((10, 10, 3), 128, dtype=np.uint8)

    assert frame_difference_score(frame, frame) == 0.0


def test_maximally_different_frames_score_one():
    black = np.zeros((10, 10, 3), dtype=np.uint8)
    white = np.full((10, 10, 3), 255, dtype=np.uint8)

    assert frame_difference_score(black, white) == 1.0


def test_score_is_the_mean_absolute_normalized_difference():
    # A known worked example, independent of the implementation: half the
    # pixels flip from 0 to 255, half stay at 0 -> mean |diff|/255 = 0.5.
    previous = np.zeros((2, 2, 3), dtype=np.uint8)
    current = np.zeros((2, 2, 3), dtype=np.uint8)
    current[0, :, :] = 255

    assert frame_difference_score(previous, current) == 0.5
