from glyphcue.adapters.transcript_export import write_ai_ready_transcript, write_readable_transcript
from glyphcue.domain.cue import Cue
from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.domain.review_state import ReviewState


def _cue(id_: str, start: float, end: float, layers, review_state=ReviewState.PENDING) -> Cue:
    return Cue(id=id_, start_time=start, end_time=end, language_layers=layers, review_state=review_state)


def test_readable_transcript_shows_timestamp_and_text_per_cue(tmp_path):
    cues = [
        _cue("c1", 0.0, 2.0, (LanguageLayer(language="en", text="Hello there"),)),
        _cue("c2", 65.5, 68.0, (LanguageLayer(language="en", text="Second line"),)),
    ]
    destination = tmp_path / "transcript.txt"

    write_readable_transcript(cues, destination)

    text = destination.read_text(encoding="utf-8")
    assert "00:00:00" in text
    assert "Hello there" in text
    assert "00:01:05" in text
    assert "Second line" in text
    # Cues stay in reading order.
    assert text.index("Hello there") < text.index("Second line")


def test_readable_transcript_excludes_discarded_cues(tmp_path):
    cues = [
        _cue("c1", 0.0, 2.0, (LanguageLayer(language="en", text="keep this"),)),
        _cue(
            "c2", 2.0, 4.0,
            (LanguageLayer(language="en", text="drop this"),),
            review_state=ReviewState.REJECTED,
        ),
    ]
    destination = tmp_path / "transcript.txt"

    write_readable_transcript(cues, destination)

    text = destination.read_text(encoding="utf-8")
    assert "keep this" in text
    assert "drop this" not in text


def test_ai_ready_transcript_reduces_timestamp_density_for_closely_spaced_cues(tmp_path):
    cues = [
        _cue("c1", 0.0, 2.0, (LanguageLayer(language="en", text="First sentence."),)),
        _cue("c2", 2.1, 4.0, (LanguageLayer(language="en", text="Second sentence."),)),
        _cue("c3", 4.1, 6.0, (LanguageLayer(language="en", text="Third sentence."),)),
        _cue("c4", 90.0, 92.0, (LanguageLayer(language="en", text="Much later sentence."),)),
    ]
    destination = tmp_path / "transcript.ai.md"

    write_ai_ready_transcript(cues, destination)

    text = destination.read_text(encoding="utf-8")
    # Closely spaced cues (well under the density-reduction gap) share
    # one timestamp heading instead of one each -- only one "##" marker
    # appears before the fourth, temporally distant, cue.
    assert text.count("##") == 2
    assert "First sentence." in text
    assert "Second sentence." in text
    assert "Third sentence." in text
    assert "Much later sentence." in text
    assert "1." not in text  # no cue numbering


def test_ai_ready_transcript_can_filter_to_selected_language_layers(tmp_path):
    cues = [
        _cue(
            "c1", 0.0, 2.0,
            (
                LanguageLayer(language="en", text="English text"),
                LanguageLayer(language="zh", text="中文文本"),
            ),
        ),
    ]
    destination = tmp_path / "transcript.ai.md"

    write_ai_ready_transcript(cues, destination, languages=("en",))

    text = destination.read_text(encoding="utf-8")
    assert "English text" in text
    assert "中文文本" not in text
