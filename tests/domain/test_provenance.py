import pytest

from glyphcue.domain.provenance import Provenance, ProvenanceKind


def test_provenance_holds_kind_and_source():
    provenance = Provenance(kind=ProvenanceKind.SUBTITLE_IMPORT, source="input.srt")

    assert provenance.kind is ProvenanceKind.SUBTITLE_IMPORT
    assert provenance.source == "input.srt"
    assert provenance.detail == {}


def test_provenance_rejects_empty_source():
    with pytest.raises(ValueError):
        Provenance(kind=ProvenanceKind.OCR_ENGINE, source="")


def test_provenance_is_immutable():
    provenance = Provenance(kind=ProvenanceKind.OCR_ENGINE, source="rapidocr")

    with pytest.raises(AttributeError):
        provenance.source = "other"
