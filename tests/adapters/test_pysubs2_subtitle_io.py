from glyphcue.adapters.pysubs2_subtitle_io import Pysubs2SubtitleFormatAdapter
from glyphcue.domain.cue import Cue
from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.domain.review_state import ReviewState

_SRT_TEXT = """1
00:00:00,000 --> 00:00:02,000
Hello <i>world</i>

2
00:00:02,500 --> 00:00:04,000
Second line
"""

_VTT_TEXT = """WEBVTT

00:00:00.000 --> 00:00:02.000
Hello VTT
"""


def test_parse_srt_strips_formatting_and_converts_ms_to_seconds(tmp_path):
    source = tmp_path / "input.srt"
    source.write_text(_SRT_TEXT, encoding="utf-8")

    observations = Pysubs2SubtitleFormatAdapter().parse(source)

    assert [o.text for o in observations] == ["Hello world", "Second line"]
    assert observations[0].start_time == 0.0
    assert observations[0].end_time == 2.0
    assert observations[1].start_time == 2.5


def test_parse_vtt_returns_observations(tmp_path):
    source = tmp_path / "input.vtt"
    source.write_text(_VTT_TEXT, encoding="utf-8")

    observations = Pysubs2SubtitleFormatAdapter().parse(source)

    assert [o.text for o in observations] == ["Hello VTT"]


def test_write_creates_a_new_file_without_touching_the_source(tmp_path):
    source = tmp_path / "input.srt"
    source.write_text(_SRT_TEXT, encoding="utf-8")
    destination = tmp_path / "output.srt"
    cues = [
        Cue(
            id="cue-1",
            start_time=0.0,
            end_time=2.0,
            language_layers=(LanguageLayer(language="en", text="Reconstructed text"),),
        )
    ]

    Pysubs2SubtitleFormatAdapter().write(cues, destination)

    assert source.read_text(encoding="utf-8") == _SRT_TEXT
    assert destination.exists()
    assert "Reconstructed text" in destination.read_text(encoding="utf-8")


def test_write_excludes_discarded_rejected_cues(tmp_path):
    destination = tmp_path / "output.srt"
    cues = [
        Cue(
            id="cue-1",
            start_time=0.0,
            end_time=2.0,
            language_layers=(LanguageLayer(language="en", text="Keep this line"),),
        ),
        Cue(
            id="cue-2",
            start_time=2.0,
            end_time=4.0,
            language_layers=(LanguageLayer(language="en", text="Discarded garbage reading"),),
            review_state=ReviewState.REJECTED,
        ),
    ]

    Pysubs2SubtitleFormatAdapter().write(cues, destination)

    exported = destination.read_text(encoding="utf-8")
    assert "Keep this line" in exported
    assert "Discarded garbage reading" not in exported


def test_write_leaves_no_temporary_file_behind(tmp_path):
    destination = tmp_path / "output.vtt"
    cues = [
        Cue(
            id="cue-1",
            start_time=0.0,
            end_time=1.0,
            language_layers=(LanguageLayer(language="en", text="hi"),),
        )
    ]

    Pysubs2SubtitleFormatAdapter().write(cues, destination)

    assert list(tmp_path.glob("*.tmp")) == []
