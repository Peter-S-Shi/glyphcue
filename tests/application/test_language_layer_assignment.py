from glyphcue.application.language_layer_assignment import assign_observations_to_languages
from glyphcue.domain.observation import Observation
from glyphcue.domain.provenance import Provenance, ProvenanceKind

_PROVENANCE = Provenance(kind=ProvenanceKind.OCR_ENGINE, source="PaddleOCR")


def _obs(id_, text, language=None, geometry=None, confidence=None):
    return Observation(
        id=id_,
        text=text,
        start_time=1.0,
        end_time=1.001,
        provenance=_PROVENANCE,
        language=language,
        confidence=confidence,
        geometry=geometry,
    )


def test_two_regions_with_reliable_language_hints_split_into_two_buckets():
    # Each engine only ever tags its own regions with its own configured
    # language (see PaddleOcrEngine), so an exact hint match against the
    # Track Group's expected languages is the most direct evidence
    # available -- no guessing needed when it's this clean.
    observations = [
        _obs("o1", "Hello there", language="en"),
        _obs("o2", "你好朋友", language="zh"),
    ]

    buckets = assign_observations_to_languages(observations, ("en", "zh"))

    assert [observation.id for observation in buckets["en"]] == ["o1"]
    assert [observation.id for observation in buckets["zh"]] == ["o2"]


def test_misleading_engine_hint_is_overridden_by_the_regions_own_script():
    # Real multi-engine verification found that a configured-language
    # OCR engine can still detect and transcribe a region in a
    # DIFFERENT script and tag it with its own (wrong, for that region)
    # configured language -- e.g. an "en"-configured engine correctly
    # reading a Chinese line but tagging it "en" anyway, since
    # PaddleOCR's detector isn't language-scoped. The region's own
    # readable text must win over that misleading hint.
    observations = [
        _obs("wrong-tag", "你好朋友", language="en"),  # correct text, wrong hint
        _obs("right-tag", "Hello there", language="en"),
    ]

    buckets = assign_observations_to_languages(observations, ("en", "zh"))

    assert [observation.id for observation in buckets["en"]] == ["right-tag"]
    assert [observation.id for observation in buckets["zh"]] == ["wrong-tag"]


def test_missing_language_hint_falls_back_to_script_detection():
    # No OCR language hint at all (e.g. a non-M4 provenance, or an
    # engine that didn't report one) -- the region's own script (Han
    # Unicode range here) is still enough to place it correctly when
    # only one expected language plausibly matches that script.
    observations = [
        _obs("o1", "Hello there", language="en"),
        _obs("o2", "你好朋友", language=None),
    ]

    buckets = assign_observations_to_languages(observations, ("en", "zh"))

    assert [observation.id for observation in buckets["en"]] == ["o1"]
    assert [observation.id for observation in buckets["zh"]] == ["o2"]


def test_no_hint_and_no_script_signal_falls_back_to_vertical_geometry_order():
    # Neither region carries a usable OCR language hint, and neither
    # region's text (plain digits) matches any known script -- the last
    # resort is vertical reading order matched against the Track
    # Group's own configured language order (top region -> first
    # configured language).
    observations = [
        _obs("bottom", "456", geometry=((0.0, 40.0), (10.0, 40.0), (10.0, 50.0), (0.0, 50.0))),
        _obs("top", "123", geometry=((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0))),
    ]

    buckets = assign_observations_to_languages(observations, ("primary", "secondary"))

    assert [observation.id for observation in buckets["primary"]] == ["top"]
    assert [observation.id for observation in buckets["secondary"]] == ["bottom"]


def test_missing_language_produces_an_empty_bucket_not_fabricated_text():
    # Only "en" text was actually found in this run -- "zh" must come
    # back as an empty bucket (the "missing layer" signal), never
    # invented text and never a crash.
    observations = [_obs("o1", "Hello there", language="en")]

    buckets = assign_observations_to_languages(observations, ("en", "zh"))

    assert [observation.id for observation in buckets["en"]] == ["o1"]
    assert buckets["zh"] == []


def test_extra_region_beyond_expected_language_count_merges_into_nearest_bucket():
    # Three regions but only two expected languages: e.g. English text
    # OCR'd as two boxes (a two-line caption). The leftover region must
    # be folded into the nearest already-assigned language, not dropped
    # and not left permanently unresolved.
    observations = [
        _obs("en-top", "Hello", language="en", geometry=((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0))),
        _obs(
            "en-bottom",
            "there",
            language=None,
            geometry=((0.0, 12.0), (10.0, 12.0), (10.0, 22.0), (0.0, 22.0)),
        ),
        _obs("zh", "你好", language="zh", geometry=((0.0, 40.0), (10.0, 40.0), (10.0, 50.0), (0.0, 50.0))),
    ]

    buckets = assign_observations_to_languages(observations, ("en", "zh"))

    assert {observation.id for observation in buckets["en"]} == {"en-top", "en-bottom"}
    assert [observation.id for observation in buckets["zh"]] == ["zh"]


def test_three_language_fixture_splits_into_three_buckets_in_configured_order():
    # No bilingual-only assumption: three (or N) expected languages must
    # work exactly like two, and buckets come back in the Track Group's
    # own configured order regardless of OCR detection order.
    observations = [
        _obs("o1", "今日は天気です", language="ja"),
        _obs("o2", "Good morning", language="en"),
        _obs("o3", "早上好", language="zh"),
    ]

    buckets = assign_observations_to_languages(observations, ("en", "zh", "ja"))

    assert list(buckets.keys()) == ["en", "zh", "ja"]
    assert [observation.id for observation in buckets["en"]] == ["o2"]
    assert [observation.id for observation in buckets["zh"]] == ["o3"]
    assert [observation.id for observation in buckets["ja"]] == ["o1"]
