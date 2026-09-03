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
    # insertion-order tie-break, AND (M11 Architecture B corrective
    # contract) must not be defaulted to whichever expected language
    # happens to be configured first either -- a tied hint vote is real,
    # undecidable ambiguity between exactly zh and ja, the same
    # fail-closed case as a pure-Han cluster with no hint evidence at
    # all (see test_pure_han_zh_ja_has_no_winner_and_preserves_ambiguity):
    # neither language gets a fabricated winner.
    observations = [
        _obs("tagged-zh", "早上好", language="zh", geometry=_same_line_geometry()),
        _obs("tagged-ja", "早上好", language="ja", geometry=_same_line_geometry()),
    ]

    buckets, ambiguous = assign_observations_to_languages(observations, ("zh", "ja"))

    assert buckets["zh"] == []
    assert buckets["ja"] == []
    assert ambiguous == {"zh", "ja"}


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


# Architecture B corrective contract (M11 Multilingual Performance
# Corrective Gate): three of the twelve acceptance cases live here
# because they're pure assign_observations_to_languages behavior, with
# no cross-frame/cue-boundary dimension. See
# test_multilingual_reconstruction.py for the temporal position-swap
# case, which needs a real multi-frame run to reproduce.


def test_numeric_punctuation_line_is_not_silently_claimed_by_elimination():
    # A bare digits/punctuation line (e.g. a burned-in timestamp) carries
    # no script evidence at all. Once "en" resolves decisively elsewhere,
    # elimination must not treat "no evidence" as "matches every
    # remaining expected language" and silently hand this line to "zh" --
    # that's a confident-looking guess with zero real support.
    observations = [
        _obs("en", "Price USD", language=None),
        _obs("digits", "2026-09-03", language=None),
    ]

    _buckets, ambiguous = assign_observations_to_languages(observations, ("en", "zh"))

    assert "zh" in ambiguous


def test_pure_han_zh_ja_has_no_winner_and_preserves_ambiguity():
    # Two pure-Han clusters, zh-or-ja Track Group, zero disambiguating
    # evidence anywhere (no Kana, no hints, nothing to eliminate
    # against). Fail-closed: neither language may get a fabricated
    # winner just because geometry has to put them somewhere.
    observations = [
        _obs("han-a", "東京", language=None),
        _obs("han-b", "天気", language=None),
    ]

    buckets, ambiguous = assign_observations_to_languages(observations, ("zh", "ja"))

    assert ambiguous == {"zh", "ja"}
    assert all(not clusters for clusters in buckets.values())


def test_mixed_script_ocr_error_is_not_silently_claimed():
    # "H你llo" is what a real OCR misread of English text corrupted by
    # one stray Han glyph looks like -- not genuine Chinese. Picking
    # "han" as this cluster's dominant script (because a Han character
    # is present at all) would silently misclassify OCR corruption as a
    # confident Chinese reading instead of surfacing it as ambiguous.
    observations = [
        _obs("corrupt-en", "H你llo", language=None),
        _obs("zh", "你好", language=None),
    ]

    _buckets, ambiguous = assign_observations_to_languages(observations, ("en", "zh"))

    assert ambiguous


def test_duplicate_universal_reads_add_votes_but_no_new_classification_information():
    # A single universal engine can read the same physical line more
    # than once per triggered frame in some pipeline configurations
    # (Architecture B doesn't currently do this, but the contract must
    # hold regardless): repeating an identical reading may add votes to
    # an existing bucket, it must never manufacture a NEW, independently
    # counted cluster/bucket shape that a single reading wouldn't have
    # produced.
    def _box(y):
        return ((0.0, y), (100.0, y), (100.0, y + 8.0), (0.0, y + 8.0))

    single = [
        _obs("zh", "你好", language=None, geometry=_box(10)),
        _obs("en", "Hello", language=None, geometry=_box(40)),
    ]
    duplicated = [
        _obs("zh-1", "你好", language=None, geometry=_box(10)),
        _obs("zh-2", "你好", language=None, geometry=_box(10)),
        _obs("en-1", "Hello", language=None, geometry=_box(40)),
        _obs("en-2", "Hello", language=None, geometry=_box(40)),
    ]

    single_buckets, single_ambiguous = assign_observations_to_languages(single, ("zh", "en"))
    dup_buckets, dup_ambiguous = assign_observations_to_languages(duplicated, ("zh", "en"))

    single_shape = {language: len(clusters) for language, clusters in single_buckets.items()}
    dup_shape = {language: len(clusters) for language, clusters in dup_buckets.items()}
    assert single_shape == dup_shape
    assert single_ambiguous == dup_ambiguous
    assert sum(len(_ids(v)) for v in dup_buckets.values()) == 2 * sum(
        len(_ids(v)) for v in single_buckets.values()
    )


# Visual-Line Clustering Corrective (M11 Architecture B, root cause of the
# DirectML h/f/c speed-vs-correctness finding): real detector geometry is
# not pixel-perfect, so two visually and linguistically DIFFERENT physical
# lines stacked close together can report Y-ranges overlapping by a few
# pixels of detection noise. Pure Y-overlap clustering merged them into one
# cluster, and _cluster_script_candidates' first-decisive-member-wins rule
# then silently attributed the WHOLE cluster (including the other line's
# real text) to one language -- the exact "layer swap" / garbled-reading
# pattern the DirectML smoke surfaced. The fix is a deterministic veto:
# no new numeric overlap threshold, just refusing to merge across a
# decisive script mismatch.


def _box(y0: float, y1: float) -> tuple:
    return ((0.0, y0), (100.0, y0), (100.0, y1), (0.0, y1))


def test_script_incompatible_regions_with_tiny_y_overlap_are_not_merged():
    # 2px of Y-overlap (28-30) between a decisively-English line and a
    # decisively-Chinese line stacked right below it -- exactly the kind
    # of detector rounding noise real geometry produces. Before the veto,
    # pure Y-overlap merged these into one cluster and one language
    # silently absorbed the other's text.
    observations = [
        _obs("en", "Hello there", geometry=_box(10, 30)),
        _obs("zh", "你好朋友", geometry=_box(28, 48)),
    ]

    buckets, ambiguous = assign_observations_to_languages(observations, ("en", "zh"))

    assert _ids(buckets["en"]) == ["en"]
    assert _ids(buckets["zh"]) == ["zh"]
    assert ambiguous == set()


def test_same_script_horizontal_fragments_with_y_overlap_still_merge():
    # Two word-level detector boxes of the SAME real English line,
    # genuinely overlapping in Y (multi-box detection of one line) --
    # the veto must not touch this: same decisive language, real overlap,
    # still one cluster.
    observations = [
        _obs("frag-1", "Hello", geometry=_box(10, 30)),
        _obs("frag-2", "there", geometry=_box(15, 35)),
    ]

    buckets, ambiguous = assign_observations_to_languages(observations, ("en", "zh"))

    assert set(_ids(buckets["en"])) == {"frag-1", "frag-2"}
    assert buckets["zh"] == []
    assert ambiguous == set()


def test_same_language_multiline_with_no_overlap_stays_separated():
    # Two real, physically separate English lines (no Y-overlap at all) --
    # governed by the overlap check exactly as before the veto existed;
    # the veto (same decisive language on both sides) never even applies.
    observations = [
        _obs("line-1", "First line", geometry=_box(10, 30)),
        _obs("line-2", "Second line", geometry=_box(50, 70)),
    ]

    buckets, ambiguous = assign_observations_to_languages(observations, ("en", "zh"))

    assert len(buckets["en"]) == 2
    assert _ids(buckets["en"]) == ["line-1", "line-2"]
    assert ambiguous == set()


def test_non_decisive_neighbor_never_triggers_a_false_veto():
    # A decisively-English region overlapping with a region carrying NO
    # script signal at all (bare digits) -- the veto only fires between
    # two DECISIVE, DIFFERENT languages; ambiguous-or-no-signal text is
    # never itself evidence of incompatibility, so this still merges by
    # geometry exactly as before the veto existed.
    observations = [
        _obs("en", "Hello there", geometry=_box(10, 30)),
        _obs("digits", "42", geometry=_box(28, 48)),
    ]

    buckets, _ambiguous = assign_observations_to_languages(observations, ("en", "zh"))

    assert set(_ids(buckets["en"])) == {"en", "digits"}
