from glyphcue.domain.observation import Observation
from glyphcue.domain.provenance import Provenance, ProvenanceKind
from glyphcue.domain.roi import ROI
from glyphcue.ui.ocr_evidence_pane import OcrEvidencePane


def _observation(id_: str, text: str, start_time: float = 0.0) -> Observation:
    return Observation(
        id=id_,
        text=text,
        start_time=start_time,
        end_time=start_time + 0.001,
        provenance=Provenance(
            kind=ProvenanceKind.OCR_ENGINE, source="PaddleOCR", detail={"engine_version": "3.7.0"}
        ),
        language="en",
        confidence=0.93,
        roi=ROI(x=0.1, y=0.8, width=0.8, height=0.15),
        frame_reference="video.mp4@1.000000s",
    )


def test_pane_lists_every_observation(qapp_guard):
    observations = [_observation("o1", "first"), _observation("o2", "second", start_time=1.0)]

    pane = OcrEvidencePane(observations)

    assert pane.list_widget.count() == 2


def test_selecting_a_row_shows_observation_detail(qapp_guard):
    observations = [_observation("o1", "hello world", start_time=1.5)]
    pane = OcrEvidencePane(observations)

    pane.list_widget.setCurrentRow(0)

    detail = pane.detail_view.toPlainText()
    assert "hello world" in detail
    assert "1.5" in detail
    assert "0.93" in detail
    assert "PaddleOCR" in detail


def test_set_observations_replaces_the_list_contents(qapp_guard):
    pane = OcrEvidencePane([_observation("o1", "first")])

    pane.set_observations([_observation("o2", "second"), _observation("o3", "third")])

    assert pane.list_widget.count() == 2


def test_empty_pane_has_no_rows(qapp_guard):
    pane = OcrEvidencePane([])

    assert pane.list_widget.count() == 0
