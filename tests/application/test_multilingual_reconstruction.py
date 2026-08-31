from glyphcue.application.multilingual_reconstruction import (
    reconstruct_multilingual_cues_for_track_group,
)
from glyphcue.application.ocr_evidence_job import STATE_TRIGGER_DETAIL_KEY
from glyphcue.domain.provenance import Provenance, ProvenanceKind
from glyphcue.domain.roi import ROI
from glyphcue.domain.track_group import TrackGroup

_PROVENANCE = Provenance(kind=ProvenanceKind.OCR_ENGINE, source="PaddleOCR")
_ROI = ROI(x=0.0, y=0.0, width=1.0, height=1.0)


def _obs(
    id_,
    text,
    start,
    end=None,
    confidence=None,
    language=None,
    frame_reference=None,
    state_trigger=None,
    geometry=None,
):
    from glyphcue.domain.observation import Observation

    detail = {STATE_TRIGGER_DETAIL_KEY: state_trigger} if state_trigger else {}
    return Observation(
        id=id_,
        text=text,
        start_time=start,
        end_time=end if end is not None else start + 0.001,
        provenance=Provenance(kind=ProvenanceKind.OCR_ENGINE, source="PaddleOCR", detail=detail),
        language=language,
        confidence=confidence,
        frame_reference=frame_reference,
        geometry=geometry,
    )


def _track_group(languages):
    return TrackGroup(id="tg-1", roi=_ROI, languages=languages)


def test_single_language_track_group_reconstructs_exactly_like_m5():
    # M6 must not regress single-language M5 behavior -- a
    # single-language Track Group's result is a byte-for-byte pass
    # through to reconstruct_cues_with_consensus, not a reimplementation
    # that happens to agree with it.
    observations = [
        _obs("o1", "Hello world", start=1.0),
        _obs("o2", "Hallo world", start=2.0),
        _obs("o3", "Hello world", start=3.0),
    ]

    cues, _diagnostics = reconstruct_multilingual_cues_for_track_group(
        observations, _track_group(("en",))
    )

    assert len(cues) == 1
    assert len(cues[0].language_layers) == 1
    assert cues[0].language_layers[0].text == "Hello world"


def test_bilingual_frame_stably_splits_into_two_language_layers():
    observations = [
        _obs("o1-en", "Hello there", start=1.0, language="en", frame_reference="v@1.0"),
        _obs("o1-zh", "你好朋友", start=1.0, language="zh", frame_reference="v@1.0"),
        _obs("o2-en", "Hello there", start=3.0, language="en", frame_reference="v@3.0"),
        _obs("o2-zh", "你好朋友", start=3.0, language="zh", frame_reference="v@3.0"),
    ]

    cues, diagnostics = reconstruct_multilingual_cues_for_track_group(
        observations, _track_group(("en", "zh"))
    )

    assert len(cues) == 1
    layers = cues[0].language_layers
    assert len(layers) == 2
    assert layers[0].language == "en"
    assert layers[0].text == "Hello there"
    assert layers[1].language == "zh"
    assert layers[1].text == "你好朋友"
    # Both layers share exactly the Cue's own timing -- no per-layer
    # timing fields exist at all (ROADMAP M6: shared Cue timing).
    assert cues[0].start_time == 1.0
    assert diagnostics[0].missing_languages == ()


def test_layer_order_is_stable_across_frames_even_when_detection_order_varies():
    # OCR happened to return the Chinese region before the English one
    # on the first frame and after it on the second -- the reconstructed
    # layer order must still always follow the Track Group's own
    # configured language order (en, zh), not detection order.
    observations = [
        _obs("o1-zh", "你好朋友", start=1.0, language="zh", frame_reference="v@1.0"),
        _obs("o1-en", "Hello there", start=1.0, language="en", frame_reference="v@1.0"),
        _obs("o2-en", "Hello there", start=3.0, language="en", frame_reference="v@3.0"),
        _obs("o2-zh", "你好朋友", start=3.0, language="zh", frame_reference="v@3.0"),
    ]

    cues, _diagnostics = reconstruct_multilingual_cues_for_track_group(
        observations, _track_group(("en", "zh"))
    )

    assert len(cues) == 1
    assert [layer.language for layer in cues[0].language_layers] == ["en", "zh"]


def test_three_language_fixture_reconstructs_into_three_layers():
    observations = [
        _obs("o-en", "Good morning", start=1.0, language="en", frame_reference="v@1.0"),
        _obs("o-zh", "早上好", start=1.0, language="zh", frame_reference="v@1.0"),
        _obs("o-ja", "おはよう", start=1.0, language="ja", frame_reference="v@1.0"),
    ]

    cues, diagnostics = reconstruct_multilingual_cues_for_track_group(
        observations, _track_group(("en", "zh", "ja"))
    )

    assert len(cues) == 1
    assert [layer.language for layer in cues[0].language_layers] == ["en", "zh", "ja"]
    assert [layer.text for layer in cues[0].language_layers] == [
        "Good morning",
        "早上好",
        "おはよう",
    ]
    assert diagnostics[0].languages_present == ("en", "zh", "ja")


def test_missing_layer_in_one_run_produces_explicit_diagnostic_not_fabricated_text():
    # The Chinese engine found nothing on this frame (asymmetric source
    # material) -- the "zh" layer must come back empty and flagged, not
    # invented from the English text or dropped from the Cue entirely.
    observations = [
        _obs("o1-en", "Hello there", start=1.0, language="en", frame_reference="v@1.0"),
    ]

    cues, diagnostics = reconstruct_multilingual_cues_for_track_group(
        observations, _track_group(("en", "zh"))
    )

    assert len(cues) == 1
    layers = cues[0].language_layers
    assert layers[0].language == "en"
    assert layers[0].text == "Hello there"
    assert layers[1].language == "zh"
    assert layers[1].text == ""
    assert diagnostics[0].missing_languages == ("zh",)
    assert diagnostics[0].languages_present == ("en",)


def test_four_language_track_group_has_no_bilingual_only_assumption():
    # Genericity check: nothing about the reconstruction path special-
    # cases "exactly two" languages.
    observations = [
        _obs("o-a", "A text", start=1.0, language="a", frame_reference="v@1.0"),
        _obs("o-b", "B text", start=1.0, language="b", frame_reference="v@1.0"),
        _obs("o-c", "C text", start=1.0, language="c", frame_reference="v@1.0"),
        _obs("o-d", "D text", start=1.0, language="d", frame_reference="v@1.0"),
    ]

    cues, _diagnostics = reconstruct_multilingual_cues_for_track_group(
        observations, _track_group(("a", "b", "c", "d"))
    )

    assert len(cues) == 1
    assert [layer.language for layer in cues[0].language_layers] == ["a", "b", "c", "d"]
    assert [layer.text for layer in cues[0].language_layers] == [
        "A text",
        "B text",
        "C text",
        "D text",
    ]
