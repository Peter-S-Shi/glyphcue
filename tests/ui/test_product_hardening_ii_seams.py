from fractions import Fraction
from pathlib import Path

import av
import numpy as np
import pytest

from glyphcue.application.cue_merge import merge_incremental_cues
from glyphcue.application.source_identity import normalize_source_id
from glyphcue.domain.cue import Cue
from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.domain.review_state import ReviewState
from glyphcue.persistence.database import connect
from glyphcue.persistence.repository import CueRepository
from glyphcue.persistence.track_group_repository import TrackGroupRepository
from glyphcue.ui.app import GlyphCueWorkbench
from glyphcue.ui.path_a_media_pane import PathAMediaPane


def _make_cue(
    id_: str,
    start: float,
    end: float,
    state: ReviewState = ReviewState.PENDING,
    text: str = "test",
    language: str = "en",
    observation_ids: tuple[str, ...] = (),
) -> Cue:
    layer = LanguageLayer(language=language, text=text, observation_ids=observation_ids)
    return Cue(id=id_, start_time=start, end_time=end, language_layers=(layer,), review_state=state)


def _make_pane(tmp_path: Path, source_id: str = "video_hardening", cues: tuple[Cue, ...] = ()) -> tuple[PathAMediaPane, CueRepository]:
    db_path = tmp_path / "hardening_test.sqlite3"
    conn = connect(db_path)
    cue_repo = CueRepository(conn)
    tg_repo = TrackGroupRepository(conn)
    if cues:
        cue_repo.save_cues_for_source(source_id, list(cues))

    pane = PathAMediaPane(tg_repo, db_path=db_path, available_languages=["en"])
    pane._source_id = source_id
    pane._video_path = Path(f"{source_id}.mp4")
    pane.qa.set_cues_and_priorities(list(cues), {}, {})
    pane._update_clean_cues_button_enabled()
    return pane, cue_repo


def _write_dummy_video(path: Path) -> None:
    container = av.open(str(path), mode="w")
    stream = container.add_stream("h264", rate=10)
    stream.width = 32
    stream.height = 32
    stream.pix_fmt = "yuv420p"
    stream.codec_context.time_base = Fraction(1, 1000)
    stream.codec_context.gop_size = 1
    for pts_ms in range(0, 300, 100):
        array = np.full((32, 32, 3), 100, dtype=np.uint8)
        frame = av.VideoFrame.from_ndarray(array, format="rgb24").reformat(format="yuv420p")
        frame.pts = pts_ms
        frame.time_base = Fraction(1, 1000)
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()


# ==============================================================================
# Risk A3 & A4: Post-Clean Manual Merge / Split Lifecycle and Protection
# ==============================================================================

def test_a3_a4_post_clean_manual_merge_and_split_lifecycle(qapp_guard, tmp_path):
    """Verifies that residual duplicates or fragments surviving conservative Clean Cues
    can be manually merged via Merge ('M') or split ('S'), and that resulting NEEDS_REVIEW
    cues are immediately persisted and protected from subsequent Clean Cues runs.
    """
    cues = (
        _make_cue("c1", 1.0, 3.0, state=ReviewState.PENDING, text="First subtitle line"),
        _make_cue("c2", 2.8, 4.5, state=ReviewState.PENDING, text="First subtitle line residual"),
        _make_cue("c3", 6.0, 9.0, state=ReviewState.PENDING, text="Long subtitle line to split"),
    )
    pane, repo = _make_pane(tmp_path, cues=cues)

    # 1. Clean Cues is run
    assert pane.clean_cues_button.isEnabled()
    pane._on_clean_cues_clicked()

    # 2. Manual Merge (A3): User merges the active cue with the next cue
    pane.qa.queue.setCurrentRow(0)
    active_cue = pane.qa.active_cue
    assert active_cue is not None

    pane.qa.merge_active_cue_with_next()

    # Verify merged cue
    merged = pane.qa.active_cue
    assert merged is not None
    assert merged.review_state == ReviewState.NEEDS_REVIEW
    assert merged.start_time == 1.0
    assert merged.end_time == 4.5
    assert "First subtitle line" in merged.language_layers[0].text

    # Verify immediate SQLite persistence
    persisted_cues = repo.list_for_source(pane._source_id)
    persisted_merged = next((c for c in persisted_cues if c.id == merged.id), None)
    assert persisted_merged is not None
    assert persisted_merged.review_state == ReviewState.NEEDS_REVIEW

    # 3. Subsequent Clean Cues invocation: merged NEEDS_REVIEW cue must be 100% protected
    pane._on_clean_cues_clicked()
    persisted_after_reclean = repo.list_for_source(pane._source_id)
    assert any(c.id == merged.id and c.review_state == ReviewState.NEEDS_REVIEW for c in persisted_after_reclean)

    # 4. Manual Split (A4): User splits cue c3 at 7.5s
    c3_row = next(i for i, c in enumerate(pane.qa.cues) if c.id == "c3")
    pane.qa.queue.setCurrentRow(c3_row)
    pane.qa.split_time_spin.setValue(7.5)
    pane.qa.split_active_cue()

    split_cues = [c for c in pane.qa.cues if c.start_time in (6.0, 7.5)]
    assert len(split_cues) == 2
    assert all(c.review_state == ReviewState.NEEDS_REVIEW for c in split_cues)

    # 5. Third Clean Cues invocation: split halves must also remain untouched
    pane._on_clean_cues_clicked()
    final_cues = repo.list_for_source(pane._source_id)
    assert any(c.start_time == 6.0 and c.end_time == 7.5 and c.review_state == ReviewState.NEEDS_REVIEW for c in final_cues)
    assert any(c.start_time == 7.5 and c.end_time == 9.0 and c.review_state == ReviewState.NEEDS_REVIEW for c in final_cues)


# ==============================================================================
# Risk A6: Unified Four-Format Export Conformance Over Mixed Review States
# ==============================================================================

def test_a6_unified_four_format_export_conformance(qapp_guard, tmp_path):
    """Verifies that all 4 supported export formats (SRT, VTT, Readable Transcript,
    AI-ready Transcript) correctly:
    1. Exclude REJECTED (discarded) cues.
    2. Include APPROVED, PENDING, and NEEDS_REVIEW cues in correct order.
    3. Generate structurally valid output without modifying or overwriting source.
    """
    cues = (
        _make_cue("c_app", 1.0, 3.0, state=ReviewState.APPROVED, text="Approved Subtitle"),
        _make_cue("c_pen", 3.5, 5.0, state=ReviewState.PENDING, text="Cleaned Pending Subtitle"),
        _make_cue("c_rev", 5.5, 7.0, state=ReviewState.NEEDS_REVIEW, text="Manually Merged Subtitle"),
        _make_cue("c_rej", 7.5, 9.0, state=ReviewState.REJECTED, text="Discarded Noise Subtitle"),
    )
    pane, _ = _make_pane(tmp_path, cues=cues)
    video_source = tmp_path / "input_video.mp4"
    _write_dummy_video(video_source)
    pane.export_controls.set_source_path(video_source)

    # 1. Export SRT
    pane.export_controls.format_combo.setCurrentText("SRT")
    srt_file = pane.export_controls.export()
    assert srt_file.exists()
    srt_content = srt_file.read_text(encoding="utf-8")
    assert "Approved Subtitle" in srt_content
    assert "Cleaned Pending Subtitle" in srt_content
    assert "Manually Merged Subtitle" in srt_content
    assert "Discarded Noise Subtitle" not in srt_content
    assert "00:00:01,000 --> 00:00:03,000" in srt_content

    # 2. Export VTT
    pane.export_controls.format_combo.setCurrentText("VTT")
    vtt_file = pane.export_controls.export()
    assert vtt_file.exists()
    vtt_content = vtt_file.read_text(encoding="utf-8")
    assert "WEBVTT" in vtt_content
    assert "Approved Subtitle" in vtt_content
    assert "Discarded Noise Subtitle" not in vtt_content
    assert "00:00:01.000 --> 00:00:03.000" in vtt_content

    # 3. Export Readable Transcript (TXT)
    pane.export_controls.format_combo.setCurrentText("Readable Transcript")
    txt_file = pane.export_controls.export()
    assert txt_file.exists()
    txt_content = txt_file.read_text(encoding="utf-8")
    assert "[00:00:01]" in txt_content
    assert "Approved Subtitle" in txt_content
    assert "Discarded Noise Subtitle" not in txt_content

    # 4. Export AI-ready Transcript (MD)
    pane.export_controls.format_combo.setCurrentText("AI-ready Transcript")
    md_file = pane.export_controls.export()
    assert md_file.exists()
    md_content = md_file.read_text(encoding="utf-8")
    assert "## 00:00:01" in md_content
    assert "Approved Subtitle" in md_content
    assert "Discarded Noise Subtitle" not in md_content

    # Source video must be untouched
    assert video_source.exists()
    assert video_source.stat().st_size > 0


# ==============================================================================
# Risk C1: Uncommitted Path A Edit Surviving Path Switching
# ==============================================================================

def test_c1_uncommitted_edit_surviving_path_switching(qapp_guard, tmp_path):
    """Verifies that typing an uncommitted edit in Path A's QA panel without pressing
    Enter/Tab is committed and persisted to SQLite when switching to Path B, and remains
    intact with NEEDS_REVIEW state upon switching back to Path A.
    """
    db_path = tmp_path / "workbench.sqlite3"
    video_path = tmp_path / "sample_c1.mp4"
    _write_dummy_video(video_path)

    workbench = GlyphCueWorkbench(db_path=db_path)
    try:
        workbench.open_video(video_path)
        pane = workbench.path_a_pane
        assert pane is not None

        cue = _make_cue("c_edit", 1.0, 3.0, state=ReviewState.PENDING, text="Original Text")
        pane.qa.set_cues_and_priorities([cue], {}, {})
        pane._cue_repository.save_cues_for_source(pane._source_id, [cue])
        pane.qa.queue.setCurrentRow(0)

        # User modifies text in the active card editor without manual commit
        active_card = pane.qa.language_layers_panel.cards[0]
        assert active_card.text_edit is not None
        active_card.text_edit.setPlainText("Modified Uncommitted Content")

        # Switch to Path B
        workbench.switch_to_mode("path_b")
        assert workbench.current_mode == "path_b"

        # Verify SQLite received the committed edit
        conn = connect(db_path)
        persisted = CueRepository(conn).list_for_source(pane._source_id)
        assert len(persisted) == 1
        assert persisted[0].language_layers[0].text == "Modified Uncommitted Content"
        assert persisted[0].review_state == ReviewState.NEEDS_REVIEW

        # Switch back to Path A
        workbench.switch_to_mode("path_a")
        assert workbench.current_mode == "path_a"
        assert pane.qa.cues[0].language_layers[0].text == "Modified Uncommitted Content"
        assert pane.qa.cues[0].review_state == ReviewState.NEEDS_REVIEW
    finally:
        workbench.close()


# ==============================================================================
# Risk E1: Reopen / Persistence / Total-Order Reconstruction
# ==============================================================================

def test_e1_reopen_and_total_ordering_invariants(qapp_guard, tmp_path):
    """Verifies that reopening a video in a fresh PathAMediaPane instance accurately
    reconstructs total ordering (start_time, end_time, id) and review states across
    APPROVED, PENDING, NEEDS_REVIEW, and REJECTED cues, with Clean Cues button state
    accurately reflecting presence of pending cues.
    """
    db_path = tmp_path / "reopen_test.sqlite3"
    conn = connect(db_path)
    cue_repo = CueRepository(conn)
    tg_repo = TrackGroupRepository(conn)
    video_path = tmp_path / "video_reopen.mp4"
    _write_dummy_video(video_path)
    source_id = normalize_source_id(video_path)

    # Insert cues intentionally unordered
    unordered_cues = [
        _make_cue("c4", 6.0, 8.0, state=ReviewState.APPROVED, text="Fourth"),
        _make_cue("c1", 1.0, 3.0, state=ReviewState.PENDING, text="First"),
        _make_cue("c2_b", 2.0, 4.0, state=ReviewState.REJECTED, text="Second B"),
        _make_cue("c2_a", 2.0, 3.5, state=ReviewState.NEEDS_REVIEW, text="Second A"),
    ]
    cue_repo.save_cues_for_source(source_id, unordered_cues)

    # Construct fresh pane instance (Session 1)
    pane1 = PathAMediaPane(tg_repo, db_path=db_path, available_languages=["en"])
    pane1.open_video(video_path)

    # Assert total order (start_time, end_time, id)
    cues_session_1 = pane1.qa.cues
    assert [c.id for c in cues_session_1] == ["c1", "c2_a", "c2_b", "c4"]
    assert cues_session_1[0].review_state == ReviewState.PENDING
    assert cues_session_1[1].review_state == ReviewState.NEEDS_REVIEW
    assert cues_session_1[2].review_state == ReviewState.REJECTED
    assert cues_session_1[3].review_state == ReviewState.APPROVED
    assert pane1.clean_cues_button.isEnabled()

    # User approves c1 (the only pending cue)
    pane1.qa.queue.setCurrentRow(0)
    pane1.qa.approve_and_advance()
    assert not pane1.clean_cues_button.isEnabled()

    # Construct another fresh pane instance (Session 2)
    pane2 = PathAMediaPane(tg_repo, db_path=db_path, available_languages=["en"])
    pane2.open_video(video_path)

    assert [c.id for c in pane2.qa.cues] == ["c1", "c2_a", "c2_b", "c4"]
    assert pane2.qa.cues[0].review_state == ReviewState.APPROVED
    # Clean cues button must remain disabled as no PENDING cues remain
    assert not pane2.clean_cues_button.isEnabled()


# ==============================================================================
# Risk E2: Multi-Cycle Incremental OCR Re-Clean Sequence
# ==============================================================================

def test_e2_incremental_ocr_multi_cycle_clean_lifecycle(qapp_guard, tmp_path):
    """Verifies a 3-cycle incremental OCR workflow:
    0–10s -> Clean -> 10–20s -> Clean -> 20–30s -> Clean.
    Asserts:
    1. Earlier non-overlapping cues are never dropped.
    2. Total ordering (start_time, end_time, id) is non-decreasing across all cycles.
    3. No uncontrolled duplicate explosion occurs.
    4. Start_time < end_time invariant holds for all surviving cues.
    5. Persistence strictly matches workspace cues across every cycle.
    """
    db_path = tmp_path / "incremental_cycle.sqlite3"
    conn = connect(db_path)
    cue_repo = CueRepository(conn)
    tg_repo = TrackGroupRepository(conn)
    source_id = "video_cycle"
    video_path = tmp_path / f"{source_id}.mp4"
    _write_dummy_video(video_path)

    pane = PathAMediaPane(tg_repo, db_path=db_path, available_languages=["en"])
    pane.open_video(video_path)

    # -------------------------------------------------------------
    # Cycle 1: 0 - 10s
    # -------------------------------------------------------------
    cycle_1_raw = [
        _make_cue("c_0_1", 1.0, 3.0, text="Intro segment A"),
        _make_cue("c_0_2", 1.2, 3.0, text="Intro segment A"),  # duplicate candidate
        _make_cue("c_0_3", 5.0, 8.0, text="Intro segment B"),
    ]
    pane.qa.set_cues_and_priorities(cycle_1_raw, {}, {})
    cue_repo.save_cues_for_source(source_id, cycle_1_raw)
    pane._update_clean_cues_button_enabled()

    pane._on_clean_cues_clicked()
    cycle_1_cleaned = list(pane.qa.cues)
    assert len(cycle_1_cleaned) >= 2
    assert all(c.start_time < c.end_time for c in cycle_1_cleaned)
    assert cue_repo.list_for_source(source_id) == cycle_1_cleaned

    # -------------------------------------------------------------
    # Cycle 2: 10 - 20s
    # -------------------------------------------------------------
    cycle_2_raw = [
        _make_cue("c_1_1", 11.0, 13.5, text="Body section part 1"),
        _make_cue("c_1_2", 11.1, 13.5, text="Body section part 1"),  # duplicate candidate
        _make_cue("c_1_3", 16.0, 19.0, text="Body section part 2"),
    ]
    cycle_2_merged = merge_incremental_cues(cycle_1_cleaned, cycle_2_raw, 10.0, 20.0)
    pane.qa.set_cues_and_priorities(cycle_2_merged, {}, {})
    cue_repo.save_cues_for_source(source_id, cycle_2_merged)
    pane._update_clean_cues_button_enabled()

    pane._on_clean_cues_clicked()
    cycle_2_cleaned = list(pane.qa.cues)

    # Earlier Cycle 1 cues must be preserved
    assert any(c.start_time == 1.0 for c in cycle_2_cleaned)
    assert any(c.start_time == 5.0 for c in cycle_2_cleaned)
    # Total ordering strictly non-decreasing
    for i in range(len(cycle_2_cleaned) - 1):
        assert (cycle_2_cleaned[i].start_time, cycle_2_cleaned[i].end_time) <= (
            cycle_2_cleaned[i + 1].start_time,
            cycle_2_cleaned[i + 1].end_time,
        )
    assert cue_repo.list_for_source(source_id) == cycle_2_cleaned

    # -------------------------------------------------------------
    # Cycle 3: 20 - 30s
    # -------------------------------------------------------------
    cycle_3_raw = [
        _make_cue("c_2_1", 21.0, 24.0, text="Conclusion segment A"),
        _make_cue("c_2_2", 26.0, 29.0, text="Conclusion segment B"),
    ]
    cycle_3_merged = merge_incremental_cues(cycle_2_cleaned, cycle_3_raw, 20.0, 30.0)
    pane.qa.set_cues_and_priorities(cycle_3_merged, {}, {})
    cue_repo.save_cues_for_source(source_id, cycle_3_merged)
    pane._update_clean_cues_button_enabled()

    pane._on_clean_cues_clicked()
    cycle_3_cleaned = list(pane.qa.cues)

    # Verify overall invariants across all 3 cycles
    assert len(cycle_3_cleaned) >= 5
    # No duplicate explosion: count should be tightly bounded (~5-7 cues)
    assert len(cycle_3_cleaned) <= 8
    # Ordering strictly monotonic
    for i in range(len(cycle_3_cleaned) - 1):
        assert cycle_3_cleaned[i].start_time <= cycle_3_cleaned[i + 1].start_time
        assert (cycle_3_cleaned[i].start_time, cycle_3_cleaned[i].end_time) <= (
            cycle_3_cleaned[i + 1].start_time,
            cycle_3_cleaned[i + 1].end_time,
        )
    # Start before end
    assert all(c.start_time < c.end_time for c in cycle_3_cleaned)
    # Database persistence is 100% in sync
    assert cue_repo.list_for_source(source_id) == cycle_3_cleaned
