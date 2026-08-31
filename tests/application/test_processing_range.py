import pytest

from glyphcue.application.processing_range import ProcessingRange


def test_default_processing_range_is_whole_media():
    processing_range = ProcessingRange()

    assert processing_range.is_whole_media() is True


def test_processing_range_resolves_against_media_duration():
    processing_range = ProcessingRange()

    start, end = processing_range.resolve(media_duration_seconds=10.0)

    assert (start, end) == (0.0, 10.0)


def test_selected_range_is_not_whole_media():
    processing_range = ProcessingRange(start_time=2.0, end_time=5.0)

    assert processing_range.is_whole_media() is False


def test_selected_range_resolves_to_its_own_bounds_regardless_of_duration():
    processing_range = ProcessingRange(start_time=2.0, end_time=5.0)

    start, end = processing_range.resolve(media_duration_seconds=100.0)

    assert (start, end) == (2.0, 5.0)


def test_resolve_rejects_a_reversed_range():
    processing_range = ProcessingRange(start_time=5.0, end_time=2.0)

    with pytest.raises(ValueError):
        processing_range.resolve(media_duration_seconds=100.0)


def test_resolve_rejects_a_zero_duration_range():
    processing_range = ProcessingRange(start_time=0.0, end_time=0.0)

    with pytest.raises(ValueError):
        processing_range.resolve(media_duration_seconds=100.0)


def test_resolve_rejects_an_end_time_beyond_the_real_media_duration():
    processing_range = ProcessingRange(start_time=0.0, end_time=50.0)

    with pytest.raises(ValueError):
        processing_range.resolve(media_duration_seconds=10.0)


def test_resolve_rejects_a_negative_start_time():
    processing_range = ProcessingRange(start_time=-1.0, end_time=5.0)

    with pytest.raises(ValueError):
        processing_range.resolve(media_duration_seconds=10.0)


def test_resolve_still_accepts_a_valid_range_within_media_duration():
    processing_range = ProcessingRange(start_time=1.0, end_time=9.0)

    start, end = processing_range.resolve(media_duration_seconds=10.0)

    assert (start, end) == (1.0, 9.0)
