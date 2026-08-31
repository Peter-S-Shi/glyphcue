import pytest

from glyphcue.domain.roi import ROI
from glyphcue.domain.track_group import TrackGroup


def _roi() -> ROI:
    return ROI(x=0.1, y=0.8, width=0.8, height=0.15)


def test_track_group_holds_roi_and_languages():
    track_group = TrackGroup(id="tg-1", roi=_roi(), languages=("ja", "en"))

    assert track_group.roi == _roi()
    assert track_group.languages == ("ja", "en")


def test_track_group_supports_a_single_language():
    track_group = TrackGroup(id="tg-1", roi=_roi(), languages=("en",))

    assert track_group.languages == ("en",)


def test_track_group_rejects_zero_languages():
    with pytest.raises(ValueError):
        TrackGroup(id="tg-1", roi=_roi(), languages=())
