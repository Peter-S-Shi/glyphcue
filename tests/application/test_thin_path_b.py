import pytest

from glyphcue.application.thin_path_b import run_thin_path_b

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
