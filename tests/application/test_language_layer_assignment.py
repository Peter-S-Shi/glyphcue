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


def _ids(clusters: list[list[Observation]]) -> list[str]:
    """Flattens a language's clusters into one id list -- for tests
    where cluster identity doesn't matter, only which raw observations
    ended up under which language."""
    return [observation.id for cluster in clusters for observation in cluster]


def test_two_regions_with_reliable_language_hints_split_into_two_buckets():
    # Each engine only ever tags its own regions with its own configured
    # language (see PaddleOcrEngine), so an exact hint match against the
    # Track Group's expected languages is the most direct evidence
    # available -- no guessing needed when it's this clean.
    observations = [
        _obs("o1", "Hello there", language="en"),
        _obs("o2", "你好朋友", language="zh"),
    ]

    buckets, ambiguous = assign_observations_to_languages(observations, ("en", "zh"))

    assert _ids(buckets["en"]) == ["o1"]
    assert _ids(buckets["zh"]) == ["o2"]
    assert ambiguous == set()


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

    buckets, ambiguous = assign_observations_to_languages(observations, ("en", "zh"))

    assert _ids(buckets["en"]) == ["right-tag"]
    assert _ids(buckets["zh"]) == ["wrong-tag"]
    assert ambiguous == set()


def test_missing_language_hint_falls_back_to_script_detection():
    # No OCR language hint at all (e.g. a non-M4 provenance, or an
    # engine that didn't report one) -- the region's own script (Han
    # Unicode range here) is still enough to place it correctly when
    # only one expected language plausibly matches that script.
    observations = [
        _obs("o1", "Hello there", language="en"),
        _obs("o2", "你好朋友", language=None),
    ]

    buckets, ambiguous = assign_observations_to_languages(observations, ("en", "zh"))

    assert _ids(buckets["en"]) == ["o1"]
    assert _ids(buckets["zh"]) == ["o2"]
    assert ambiguous == set()


def test_no_hint_and_no_script_signal_falls_back_to_vertical_geometry_order():
    # Neither region carries a usable OCR language hint, and neither
    # region's text (plain digits) matches any known script -- the last
    # resort is vertical reading order matched against the Track
    # Group's own configured language order (top region -> first
    # configured language). This is a genuine geometry-only guess, so
    # both languages come back flagged ambiguous.
    observations = [
        _obs("bottom", "456", geometry=((0.0, 40.0), (10.0, 40.0), (10.0, 50.0), (0.0, 50.0))),
        _obs("top", "123", geometry=((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0))),
    ]

    buckets, ambiguous = assign_observations_to_languages(observations, ("primary", "secondary"))

    assert _ids(buckets["primary"]) == ["top"]
    assert _ids(buckets["secondary"]) == ["bottom"]
    assert ambiguous == {"primary", "secondary"}


def test_missing_language_produces_an_empty_bucket_not_fabricated_text():
    # Only "en" text was actually found in this run -- "zh" must come
    # back as an empty bucket (the "missing layer" signal), never
    # invented text and never a crash.
    observations = [_obs("o1", "Hello there", language="en")]

    buckets, ambiguous = assign_observations_to_languages(observations, ("en", "zh"))

    assert _ids(buckets["en"]) == ["o1"]
    assert buckets["zh"] == []
    assert ambiguous == set()


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

    buckets, ambiguous = assign_observations_to_languages(observations, ("en", "zh"))

    assert set(_ids(buckets["en"])) == {"en-top", "en-bottom"}
    assert _ids(buckets["zh"]) == ["zh"]
    # Both English regions resolve decisively via script on their own
    # (plain Latin text) -- no geometry guessing was actually needed.
    assert ambiguous == set()


def test_three_language_fixture_splits_into_three_buckets_in_configured_order():
    # No bilingual-only assumption: three (or N) expected languages must
    # work exactly like two, and buckets come back in the Track Group's
    # own configured order regardless of OCR detection order.
    observations = [
        _obs("o1", "今日は天気です", language="ja"),
        _obs("o2", "Good morning", language="en"),
        _obs("o3", "早上好", language="zh"),
    ]

    buckets, ambiguous = assign_observations_to_languages(observations, ("en", "zh", "ja"))

    assert list(buckets.keys()) == ["en", "zh", "ja"]
    assert _ids(buckets["en"]) == ["o2"]
    assert _ids(buckets["zh"]) == ["o3"]
    assert _ids(buckets["ja"]) == ["o1"]
    assert ambiguous == set()


def _same_line_geometry():
    return ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0))


def test_han_hint_tie_stays_unresolved_by_classification_not_broken_by_counter_order():
    # Two engines' readings of the SAME real physical line (matching
    # geometry, so they cluster together), pure Han text, hints tied
    # 1:1 between zh and ja -- there is genuinely no decisive evidence.
    # This must NOT be silently resolved by Counter.most_common()'s
    # insertion-order tie-break; it must fall through to the geometry
    # fallback (here, the only cluster, so it lands under whichever
    # configured language comes first) and be flagged ambiguous, never
    # quietly guessed as "whichever tag was seen first."
    observations = [
        _obs("tagged-zh", "早上好", language="zh", geometry=_same_line_geometry()),
        _obs("tagged-ja", "早上好", language="ja", geometry=_same_line_geometry()),
    ]

    buckets, ambiguous = assign_observations_to_languages(observations, ("zh", "ja"))

    # The single cluster (both readings of one real line) landed
    # entirely under "zh" -- the first configured language, since
    # geometry fallback pairs unresolved clusters against
    # expected_languages' own order -- and is flagged ambiguous, since
    # nothing decisive placed it there. "ja" is left genuinely empty.
    assert set(_ids(buckets["zh"])) == {"tagged-zh", "tagged-ja"}
    assert buckets["ja"] == []
    assert ambiguous == {"zh"}


def test_han_tie_resolution_is_independent_of_engine_input_order():
    # The same tied-hint evidence, permuted -- the final assignment
    # must be identical regardless of which order the observations
    # arrived in (never engine-insertion-order dependent).
    forward = [
        _obs("a", "早上好", language="zh", geometry=_same_line_geometry()),
        _obs("b", "早上好", language="ja", geometry=_same_line_geometry()),
    ]
    reversed_order = list(reversed(forward))

    forward_buckets, forward_ambiguous = assign_observations_to_languages(forward, ("zh", "ja"))
    reversed_buckets, reversed_ambiguous = assign_observations_to_languages(
        reversed_order, ("zh", "ja")
    )

    forward_shape = {language: sorted(_ids(clusters)) for language, clusters in forward_buckets.items()}
    reversed_shape = {
        language: sorted(_ids(clusters)) for language, clusters in reversed_buckets.items()
    }
    assert forward_shape == reversed_shape
    assert forward_ambiguous == reversed_ambiguous


def test_kana_cluster_claiming_ja_lets_a_plain_han_cluster_resolve_to_zh():
    # en + zh + ja Track Group. The Kana cluster is decisive on its own
    # ("ja"). Once "ja" is claimed, the separate pure-Han Chinese
    # cluster has only "zh" left after elimination -- no hint vote is
    # even needed, and the result must be deterministic regardless of
    # cluster processing order.
    observations = [
        _obs("en", "Good morning", language="en"),
        _obs("han", "早上好", language=None),  # pure Han, no hint at all
        _obs("kana", "おはよう", language=None),  # Kana -- decisively ja
    ]

    buckets, ambiguous = assign_observations_to_languages(observations, ("en", "zh", "ja"))

    assert _ids(buckets["en"]) == ["en"]
    assert _ids(buckets["zh"]) == ["han"]
    assert _ids(buckets["ja"]) == ["kana"]
    assert ambiguous == set()
