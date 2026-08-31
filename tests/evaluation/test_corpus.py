"""Milestone 10 evaluation corpus manifest schema.

Ground truth for every assertion here is a hand-written literal, not a
value derived from `load_corpus_manifest`'s own parsing logic --
independent of the code under test, per the tdd skill's rule against
tautological assertions.
"""

import json

import pytest

from glyphcue.evaluation.corpus import (
    CorpusEntry,
    CorpusVisibility,
    GroundTruthCue,
    load_corpus,
    load_corpus_manifest,
)


def test_load_corpus_manifest_parses_one_public_entry(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "id": "demo-clip-1",
                        "video_path": "corpus/demo-clip-1.mp4",
                        "segment_start_seconds": 30.0,
                        "segment_end_seconds": 180.0,
                        "languages": ["en"],
                        "visibility": "public",
                        "ground_truth_cues": [
                            {
                                "start_time": 31.5,
                                "end_time": 34.0,
                                "text": "The quick brown fox jumps over the lazy dog.",
                                "language": "en",
                            }
                        ],
                        "notes": "Public demo-safe sample.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    entries = load_corpus_manifest(manifest_path)

    assert entries == (
        CorpusEntry(
            id="demo-clip-1",
            video_path="corpus/demo-clip-1.mp4",
            segment_start_seconds=30.0,
            segment_end_seconds=180.0,
            languages=("en",),
            visibility=CorpusVisibility.PUBLIC,
            ground_truth_cues=(
                GroundTruthCue(
                    start_time=31.5,
                    end_time=34.0,
                    text="The quick brown fox jumps over the lazy dog.",
                    language="en",
                ),
            ),
            notes="Public demo-safe sample.",
        ),
    )


def test_load_corpus_manifest_rejects_reversed_segment(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "id": "bad-clip",
                        "video_path": "corpus/bad-clip.mp4",
                        "segment_start_seconds": 90.0,
                        "segment_end_seconds": 90.0,
                        "languages": ["en"],
                        "visibility": "public",
                        "ground_truth_cues": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="segment end must be after segment start"):
        load_corpus_manifest(manifest_path)


def test_load_corpus_manifest_reports_missing_required_field_clearly(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        # "id" is missing.
                        "video_path": "corpus/no-id.mp4",
                        "segment_start_seconds": 0.0,
                        "segment_end_seconds": 60.0,
                        "languages": ["en"],
                        "visibility": "public",
                        "ground_truth_cues": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing required field 'id'"):
        load_corpus_manifest(manifest_path)


def _write_manifest(path, entry_id, visibility):
    path.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "id": entry_id,
                        "video_path": f"corpus/{entry_id}.mp4",
                        "segment_start_seconds": 0.0,
                        "segment_end_seconds": 60.0,
                        "languages": ["en"],
                        "visibility": visibility,
                        "ground_truth_cues": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def test_load_corpus_merges_multiple_manifests(tmp_path):
    public_path = tmp_path / "public.json"
    private_path = tmp_path / "private.json"
    _write_manifest(public_path, "public-clip", "public")
    _write_manifest(private_path, "private-clip", "private")

    entries = load_corpus(public_path, private_path)

    assert {entry.id for entry in entries} == {"public-clip", "private-clip"}


def test_load_corpus_rejects_duplicate_entry_id_across_manifests(tmp_path):
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    _write_manifest(first_path, "same-id", "public")
    _write_manifest(second_path, "same-id", "private")

    with pytest.raises(ValueError, match="duplicate corpus entry id 'same-id'"):
        load_corpus(first_path, second_path)
