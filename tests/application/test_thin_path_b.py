import pytest

from glyphcue.application.thin_path_b import parse_and_reconstruct, run_thin_path_b

_NORMAL_SRT = """1
00:00:00,000 --> 00:00:02,000
First complete sentence.

2
00:00:02,100 --> 00:00:04,000
Second complete sentence.

3
00:00:04,100 --> 00:00:06,000
Third complete sentence.
"""

_ROLLING_SRT = """1
00:00:00,000 --> 00:00:02,000
Hello

2
00:00:01,000 --> 00:00:04,000
Hello world

3
00:00:03,000 --> 00:00:06,000
Hello world, how are you
"""


def test_normal_subtitle_file_round_trips_unchanged_text(tmp_path):
    source = tmp_path / "normal.srt"
    source.write_text(_NORMAL_SRT, encoding="utf-8")

    destination = run_thin_path_b(source)

    output_text = destination.read_text(encoding="utf-8")
    assert "First complete sentence." in output_text
    assert "Second complete sentence." in output_text
    assert "Third complete sentence." in output_text


def test_rolling_subtitle_file_produces_a_merged_cue(tmp_path):
    source = tmp_path / "rolling.srt"
    source.write_text(_ROLLING_SRT, encoding="utf-8")

    destination = run_thin_path_b(source)

    output_text = destination.read_text(encoding="utf-8")
    assert "Hello world, how are you" in output_text
    assert output_text.count("-->") == 1


def test_original_source_file_is_never_modified(tmp_path):
    source = tmp_path / "rolling.srt"
    source.write_text(_ROLLING_SRT, encoding="utf-8")

    run_thin_path_b(source)

    assert source.read_text(encoding="utf-8") == _ROLLING_SRT


def test_output_is_written_to_a_different_file(tmp_path):
    source = tmp_path / "normal.srt"
    source.write_text(_NORMAL_SRT, encoding="utf-8")

    destination = run_thin_path_b(source)

    assert destination != source
    assert destination.exists()


def test_cjk_rolling_subtitle_file_merges_via_character_overlap(tmp_path):
    # Japanese SRT with no spaces between words -- exercises the same
    # character-level (not whitespace-token) overlap detection through
    # real file I/O, not just the in-memory reconstruction unit test.
    cjk_srt = (
        "1\n00:00:00,000 --> 00:00:02,000\nこんにちは\n\n"
        "2\n00:00:01,000 --> 00:00:04,000\nこんにちは世界\n\n"
        "3\n00:00:03,000 --> 00:00:06,000\nこんにちは世界、ようこそ\n"
    )
    source = tmp_path / "cjk.srt"
    source.write_text(cjk_srt, encoding="utf-8")

    destination = run_thin_path_b(source)

    output_text = destination.read_text(encoding="utf-8")
    assert "こんにちは世界、ようこそ" in output_text
    assert output_text.count("-->") == 1
    assert source.read_text(encoding="utf-8") == cjk_srt


def test_refuses_to_write_over_the_source_file(tmp_path):
    source = tmp_path / "normal.srt"
    source.write_text(_NORMAL_SRT, encoding="utf-8")

    with pytest.raises(ValueError):
        run_thin_path_b(source, destination=source)


_SRT_WITH_ONE_INVALID_EVENT = """1
00:00:00,000 --> 00:00:02,000
First valid line.

2
00:00:03,000 --> 00:00:02,500
Invalid inverted timing line.

3
00:00:04,000 --> 00:00:06,000
Second valid line.
"""


def test_parse_and_reconstruct_recovers_valid_cues_and_surfaces_the_invalid_event(tmp_path):
    # The application flow (parse_and_reconstruct) must not drop the
    # import warning the adapter produces for a skipped invalid event --
    # both legitimate captions are still recoverable AND the bad one is
    # visible, not silently discarded.
    source = tmp_path / "mixed.srt"
    source.write_text(_SRT_WITH_ONE_INVALID_EVENT, encoding="utf-8")

    cues, _observations_by_id, _diagnostics_by_cue_id, import_warnings = parse_and_reconstruct(source)

    texts = [cue.language_layers[0].text for cue in cues]
    assert texts == ["First valid line.", "Second valid line."]
    assert len(import_warnings) == 1
    assert import_warnings[0].source_index == 1
