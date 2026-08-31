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
