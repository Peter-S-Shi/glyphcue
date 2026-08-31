from glyphcue.application.pipeline_metrics import PipelineMetrics


def test_metrics_default_to_zero():
    metrics = PipelineMetrics()

    assert metrics.frames_analyzed == 0
    assert metrics.ocr_calls == 0
    assert metrics.observations_created == 0
    assert metrics.elapsed_seconds == 0.0
    assert metrics.media_seconds_processed == 0.0


def test_metrics_fields_are_mutable_for_in_place_accumulation_during_a_job():
    metrics = PipelineMetrics()

    metrics.frames_analyzed += 1
    metrics.ocr_calls += 1
    metrics.observations_created += 2
    metrics.elapsed_seconds = 1.5
    metrics.media_seconds_processed = 3.0

    assert metrics.frames_analyzed == 1
    assert metrics.ocr_calls == 1
    assert metrics.observations_created == 2


def test_ocr_calls_per_minute_is_computed_from_elapsed_seconds():
    metrics = PipelineMetrics(ocr_calls=30, elapsed_seconds=15.0)

    assert metrics.ocr_calls_per_minute == 120.0


def test_ocr_calls_per_minute_is_zero_when_no_time_has_elapsed():
    metrics = PipelineMetrics(ocr_calls=5, elapsed_seconds=0.0)

    assert metrics.ocr_calls_per_minute == 0.0


def test_effective_processing_speed_is_media_seconds_per_wall_clock_second():
    # Processed 20s of media in 5s of wall-clock time -> 4x real-time.
    metrics = PipelineMetrics(media_seconds_processed=20.0, elapsed_seconds=5.0)

    assert metrics.effective_processing_speed == 4.0


def test_effective_processing_speed_is_zero_when_no_time_has_elapsed():
    metrics = PipelineMetrics(media_seconds_processed=20.0, elapsed_seconds=0.0)

    assert metrics.effective_processing_speed == 0.0
