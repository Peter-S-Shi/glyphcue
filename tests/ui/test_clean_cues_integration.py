from pathlib import Path
from unittest.mock import MagicMock, patch

from glyphcue.application.pipeline_metrics import PipelineMetrics
from glyphcue.domain.cue import Cue
from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.domain.observation import Observation
from glyphcue.domain.provenance import Provenance, ProvenanceKind
from glyphcue.domain.review_state import ReviewState
from glyphcue.domain.roi import ROI
from glyphcue.domain.track_group import TrackGroup
from glyphcue.jobs.job import JobState
from glyphcue.persistence.database import connect
from glyphcue.persistence.observation_repository import ObservationRepository
from glyphcue.persistence.repository import CueRepository
from glyphcue.persistence.track_group_repository import TrackGroupRepository
from glyphcue.ui.path_a_media_pane import PathAMediaPane


def _make_cue(id_, start, end, state=ReviewState.PENDING, text="test", observation_ids=()):
    layer = LanguageLayer(language="en", text=text, observation_ids=observation_ids)
    return Cue(id=id_, start_time=start, end_time=end, language_layers=(layer,), review_state=state)


def _make_multilang_cue(id_, start, end, state=ReviewState.PENDING):
    layers = (
        LanguageLayer(language="en", text="hello"),
        LanguageLayer(language="zh", text="你好"),
    )
    return Cue(id=id_, start_time=start, end_time=end, language_layers=layers, review_state=state)


def _make_pane(tmp_path, source_id="video_a", cues=()):
    db_path = tmp_path / "test.sqlite3"
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


def test_clean_cues_button_disabled_with_no_current_video(qapp_guard, tmp_path):
    pane, _ = _make_pane(tmp_path, cues=[])
    pane._source_id = None
    pane._update_clean_cues_button_enabled()

    assert not pane.clean_cues_button.isEnabled()

    # Safe no-op even if clicked directly.
    pane._on_clean_cues_clicked()
    assert pane.qa.cues == []


def test_clean_cues_button_disabled_when_no_eligible_cues(qapp_guard, tmp_path):
    cues = [
        _make_cue("c1", 0.0, 1.0, state=ReviewState.APPROVED),
        _make_cue("c2", 1.0, 2.0, state=ReviewState.REJECTED),
    ]
    pane, cue_repo = _make_pane(tmp_path, cues=cues)

    assert not pane.clean_cues_button.isEnabled()

    pane._on_clean_cues_clicked()

    # Safe no-op: nothing changed.
    assert {c.id for c in pane.qa.cues} == {"c1", "c2"}
    assert {c.id for c in cue_repo.list_for_source("video_a")} == {"c1", "c2"}


def test_clean_cues_button_enabled_when_eligible_cues_exist(qapp_guard, tmp_path):
    cues = [_make_cue("c1", 0.0, 1.0)]
    pane, _ = _make_pane(tmp_path, cues=cues)

    assert pane.clean_cues_button.isEnabled()


def test_clean_cues_button_disables_when_cues_reviewed_via_qa(qapp_guard, tmp_path):
    cues = [_make_cue("c1", 0.0, 1.0, state=ReviewState.PENDING)]
    pane, _ = _make_pane(tmp_path, cues=cues)
    assert pane.clean_cues_button.isEnabled()

    # User approves the cue via QA workbench
    pane.qa.approve_and_advance()
    assert not pane.clean_cues_button.isEnabled()


def test_clean_cues_merges_duplicate_and_updates_workspace_and_persistence(qapp_guard, tmp_path):
    cues = [
        _make_cue("c1", 0.0, 1.0, text="hello world", observation_ids=("o1",)),
        _make_cue("c2", 1.0, 2.0, text="hello world", observation_ids=("o2",)),
    ]
    pane, cue_repo = _make_pane(tmp_path, cues=cues)

    pane._on_clean_cues_clicked()

    assert len(pane.qa.cues) == 1
    merged = pane.qa.cues[0]
    assert merged.start_time == 0.0
    assert merged.end_time == 2.0
    assert merged.language_layers[0].text == "hello world"
    assert merged.review_state == ReviewState.PENDING
    assert merged.start_time < merged.end_time

    # Persistence reflects the same result (source-of-truth check).
    persisted = cue_repo.list_for_source("video_a")
    assert len(persisted) == 1
    assert persisted[0].language_layers[0].text == "hello world"
    for cue in persisted:
        assert cue.start_time < cue.end_time


def test_clean_cues_only_touches_current_video_source(qapp_guard, tmp_path):
    db_path = tmp_path / "test.sqlite3"
    conn = connect(db_path)
    cue_repo = CueRepository(conn)
    tg_repo = TrackGroupRepository(conn)

    source_a = "video_a"
    source_b = "video_b"
    cues_a = [
        _make_cue("ca1", 0.0, 1.0, text="dup"),
        _make_cue("ca2", 1.0, 2.0, text="dup"),
    ]
    cues_b = [
        _make_cue("cb1", 0.0, 1.0, text="dup"),
        _make_cue("cb2", 1.0, 2.0, text="dup"),
    ]
    cue_repo.save_cues_for_source(source_a, cues_a)
    cue_repo.save_cues_for_source(source_b, cues_b)

    pane = PathAMediaPane(tg_repo, db_path=db_path, available_languages=["en"])
    pane._source_id = source_a
    pane._video_path = Path("video_a.mp4")
    pane.qa.set_cues_and_priorities(cues_a, {}, {})
    pane._update_clean_cues_button_enabled()

    pane._on_clean_cues_clicked()

    assert len(cue_repo.list_for_source(source_a)) == 1
    # Other video's cues are completely untouched.
    assert cue_repo.list_for_source(source_b) == cues_b


def test_clean_cues_second_click_is_idempotent(qapp_guard, tmp_path):
    cues = [
        _make_cue("c1", 0.0, 1.0, text="hello world", observation_ids=("o1",)),
        _make_cue("c2", 1.0, 2.0, text="hello world", observation_ids=("o2",)),
        _make_cue("c3", 2.0, 3.0, text="a distinct caption", observation_ids=("o3",)),
    ]
    pane, cue_repo = _make_pane(tmp_path, cues=cues)

    pane._on_clean_cues_clicked()
    first_result = list(pane.qa.cues)

    pane._on_clean_cues_clicked()
    second_result = list(pane.qa.cues)

    assert len(first_result) == len(second_result)
    for a, b in zip(
        sorted(first_result, key=lambda c: c.start_time),
        sorted(second_result, key=lambda c: c.start_time),
    ):
        assert a.id == b.id
        assert a.language_layers[0].text == b.language_layers[0].text
        assert a.review_state == b.review_state


def test_clean_cues_preserves_approved_rejected_and_needs_review_unchanged(qapp_guard, tmp_path):
    approved = _make_cue("approved", 0.0, 1.0, state=ReviewState.APPROVED, text="hello world")
    rejected = _make_cue("rejected", 1.0, 2.0, state=ReviewState.REJECTED, text="hello world")
    needs_review = _make_cue("needs_review", 2.0, 3.0, state=ReviewState.NEEDS_REVIEW, text="hello world")
    eligible = _make_cue("eligible", 3.0, 4.0, text="hello world")
    pane, cue_repo = _make_pane(
        tmp_path, cues=[approved, rejected, needs_review, eligible]
    )

    pane._on_clean_cues_clicked()

    by_id = {c.id: c for c in pane.qa.cues}
    assert by_id["approved"] == approved
    assert by_id["rejected"] == rejected
    assert by_id["needs_review"] == needs_review
    assert by_id["eligible"].review_state == ReviewState.PENDING


def test_clean_cues_merges_duplicate_bilingual_cues_and_splits_layers_back_correctly(qapp_guard, tmp_path):
    """Bilingual (multi-language-layer) Cues are cleaner-eligible too --
    see cue_cleaning.py's module docstring for how each language layer's
    text is losslessly reconstructed after the frozen Cleaner's flat-text
    merge, without guessing at which layer a surviving line belongs to."""
    multi1 = _make_multilang_cue("m1", 0.0, 1.0)
    multi2 = _make_multilang_cue("m2", 1.0, 2.0)
    pane, cue_repo = _make_pane(tmp_path, cues=[multi1, multi2])

    assert pane.clean_cues_button.isEnabled()

    pane._on_clean_cues_clicked()

    assert len(pane.qa.cues) == 1
    merged = pane.qa.cues[0]
    assert merged.start_time == 0.0
    assert merged.end_time == 2.0
    assert merged.start_time < merged.end_time
    layers = {layer.language: layer.text for layer in merged.language_layers}
    assert layers == {"en": "hello", "zh": "你好"}


def test_clean_cues_leaves_distinct_bilingual_cues_untouched(qapp_guard, tmp_path):
    distinct1 = Cue(
        id="m1", start_time=0.0, end_time=1.0,
        language_layers=(
            LanguageLayer(language="en", text="first line"),
            LanguageLayer(language="zh", text="第一行"),
        ),
        review_state=ReviewState.PENDING,
    )
    distinct2 = Cue(
        id="m2", start_time=5.0, end_time=6.0,
        language_layers=(
            LanguageLayer(language="en", text="second line"),
            LanguageLayer(language="zh", text="第二行"),
        ),
        review_state=ReviewState.PENDING,
    )
    pane, cue_repo = _make_pane(tmp_path, cues=[distinct1, distinct2])

    pane._on_clean_cues_clicked()

    assert {c.id for c in pane.qa.cues} == {"m1", "m2"}
    assert all(len(c.language_layers) == 2 for c in pane.qa.cues)


def test_clean_cues_result_stays_chronologically_ordered(qapp_guard, tmp_path):
    cues = [
        _make_cue("late", 5.0, 6.0, text="one"),
        _make_cue("early", 0.0, 1.0, text="two"),
        _make_cue("mid", 2.0, 3.0, text="three", state=ReviewState.APPROVED),
    ]
    pane, _ = _make_pane(tmp_path, cues=cues)

    pane._on_clean_cues_clicked()

    starts = [c.start_time for c in pane.qa.cues]
    assert starts == sorted(starts)
    for cue in pane.qa.cues:
        assert cue.start_time < cue.end_time


def test_clean_cues_queue_has_no_duplicate_rows_immediately_after_click_no_restart(qapp_guard, tmp_path):
    """Human QA Case A: a persistent caption observed across several
    near-duplicate OCR frames, interrupted by one non-absorbable garbled
    frame, could previously survive Clean Cues as two text-identical
    domain Cues (see test_noise_split_persistent_caption_does_not_survive_as_duplicate_text
    in test_cue_cleaning.py for the minimized adapter-level repro). Human
    QA additionally reported the QA queue looking transiently
    duplicated/out-of-order immediately after clicking Clean Cues, before
    any restart. This asserts the queue is correct immediately: exactly
    one row per current self.qa.cues entry, in chronological order, with
    matching ids -- no restart needed to "normalize" it."""
    caption = "我直接从三个最具体的问题拆解"
    noisy = caption[: len(caption) // 2] + "口"
    cues = [
        _make_cue("c1", 0.00, 0.09, text=caption, observation_ids=("o1",)),
        _make_cue("c2", 0.09, 0.18, text=noisy, observation_ids=("o2",)),
        _make_cue("c3", 0.18, 0.27, text=caption, observation_ids=("o3",)),
    ]
    pane, cue_repo = _make_pane(tmp_path, cues=cues)

    pane._on_clean_cues_clicked()

    # No restart, no re-read from the repository -- inspect the live
    # in-memory workspace and queue widget directly.
    workspace_cues = pane.qa.cues
    queue_ids = [pane.qa.cue_id_for_row(row) for row in range(pane.qa.queue.count())]

    assert len(queue_ids) == len(workspace_cues)
    assert queue_ids == [c.id for c in workspace_cues]
    assert len(set(queue_ids)) == len(queue_ids), f"duplicate rows in queue: {queue_ids}"

    starts = [c.start_time for c in workspace_cues]
    assert starts == sorted(starts)

    texts = [layer.text for c in workspace_cues for layer in c.language_layers]
    assert texts.count(caption) <= 1, f"caption duplicated in live workspace: {texts}"

    # Persistence agrees with the live workspace (no restart needed).
    persisted = cue_repo.list_for_source("video_a")
    assert {c.id for c in persisted} == {c.id for c in workspace_cues}


def test_export_controls_reads_cleaned_workspace_state(qapp_guard, tmp_path):
    """All four export formats share the same `get_cues` seam
    (`self.qa.cues`), so proving this callback reflects the cleaned
    result covers SRT/VTT/Readable/AI-ready export consumption without
    duplicating a per-format test."""
    cues = [
        _make_cue("c1", 0.0, 1.0, text="hello world"),
        _make_cue("c2", 1.0, 2.0, text="hello world"),
    ]
    pane, _ = _make_pane(tmp_path, cues=cues)

    pane._on_clean_cues_clicked()

    exported_cues = pane.export_controls._get_cues()
    assert exported_cues == pane.qa.cues
    assert len(exported_cues) == 1
    assert exported_cues[0].language_layers[0].text == "hello world"


def _assert_queue_strictly_monotonic(pane):
    queue = pane.qa.queue
    count = queue.count()
    if count <= 1:
        return
    cues_by_id = {c.id: c for c in pane.qa.cues}
    starts = []
    for r in range(count):
        cid = pane.qa.cue_id_for_row(r)
        assert cid in cues_by_id, f"Queue item at row {r} (id={cid}) not in workspace cues"
        starts.append(cues_by_id[cid].start_time)
    for i in range(len(starts) - 1):
        assert starts[i] <= starts[i + 1], (
            f"Queue is not monotonic at row {i}: {starts[i]} > {starts[i + 1]} (full starts: {starts})"
        )


def test_incremental_ocr_clean_extend_range_clean_and_restart_sequence(qapp_guard, tmp_path):
    """Human QA Case A regression: multi-range incremental OCR followed by Clean Cues
    at each stage and an eventual application restart.

    Verifies that:
    1. Across each range extension, Cues and review queue items remain strictly chronological.
    2. Clicking Clean Cues preserves chronological order and never introduces duplicate or non-monotonic Cues.
    3. Reopening the video (restart) produces identical snapshots across CueRepository,
       self.qa.cues, and QListWidget row items with zero duplicated IDs and strict monotonicity.
    """
    db_path = tmp_path / "test_incremental.sqlite3"
    conn = connect(db_path)
    cue_repo = CueRepository(conn)
    tg_repo = TrackGroupRepository(conn)
    obs_repo = ObservationRepository(conn)
    video_file = tmp_path / "test_sample_a.mp4"
    video_file.write_bytes(b"dummy")
    from glyphcue.application.source_identity import normalize_source_id
    source_id = normalize_source_id(video_file)

    pane = PathAMediaPane(tg_repo, db_path=db_path, available_languages=["zh"])
    with patch("glyphcue.ui.path_a_media_pane.probe_media") as mock_probe:
        mock_probe.return_value = MagicMock(width=1920, height=1080, duration_seconds=60.0, codec_name="h264")
        pane.open_video(video_file)
    pane._current_track_group = TrackGroup(id=pane._track_group_id, roi=ROI(0, 0, 1, 1), languages=("zh",))

    def _run_ocr_range(start_t, end_t, run_id, obs_specs):
        pane.limit_processing_range_checkbox.setChecked(True)
        pane.processing_range_start_spin.setValue(start_t)
        pane.processing_range_end_spin.setValue(end_t)
        pane._processing_range = pane.current_processing_range()
        pane._current_processing_end_time = end_t
        pane.current_evidence_run_id = run_id

        for oid, ost, oet, otxt in obs_specs:
            obs = Observation(
                id=oid,
                text=otxt,
                start_time=ost,
                end_time=oet,
                provenance=Provenance(ProvenanceKind.OCR_ENGINE, "test", {}),
                language="zh",
                confidence=1.0,
                roi=ROI(0, 0, 1, 1),
                geometry=None,
                frame_reference=f"frame_{ost:.2f}",
            )
            obs_repo.add(obs, run_id, source_id)

        mock_job = MagicMock()
        mock_job.state = JobState.SUCCEEDED
        pane.current_ocr_job = mock_job
        pane._ocr_start_time = 0.0
        pane.ocr_metrics = PipelineMetrics()
        with patch("glyphcue.ui.path_a_media_pane.play_ocr_completion_chime"):
            pane._on_ocr_finished()

    # Step 1: Range 0.0 - 10.0s
    _run_ocr_range(
        0.0, 10.0, "run-1",
        [
            ("o1", 0.0, 1.23, "AI现在这么火"),
            ("o2", 1.23, 3.47, "文科商科背景的会不会焦虑"),
            ("o3", 3.47, 4.93, "没有技术背景应该怎么办呢？"),
            ("o4", 8.63, 9.97, "我直接从三个最具体的问题拆解"),
        ]
    )
    assert len(pane.qa.cues) == 4
    pane._on_clean_cues_clicked()
    assert len(pane.qa.cues) == 4
    _assert_queue_strictly_monotonic(pane)

    # Step 2: Extend Range 10.0 - 20.0s (via Resume from Last End)
    assert pane.resume_from_last_end_button.isEnabled()
    pane._on_resume_from_last_end_clicked()
    _run_ocr_range(
        10.0, 20.0, "run-2",
        [
            ("o5_a", 10.00, 10.40, "我直接从三个最具体的问题拆解d"),
            ("o5_b", 10.40, 11.07, "我直接从三个最具体的问题拆解"),
            ("o6", 11.07, 13.10, "非技术背景要怎么判断"),
            ("o7", 17.13, 17.27, "人"),
            ("o8", 17.80, 18.10, "1"),
            ("o9", 18.83, 18.97, "M"),
        ]
    )
    _assert_queue_strictly_monotonic(pane)
    pane._on_clean_cues_clicked()
    _assert_queue_strictly_monotonic(pane)

    # Step 3: Extend Range 20.0 - 30.0s
    pane._on_resume_from_last_end_clicked()
    _run_ocr_range(
        20.0, 30.0, "run-3",
        [
            ("o10", 21.33, 21.80, "八"),
            ("o11", 23.33, 25.03, "一有没有必要入局"),
            ("o12", 25.03, 26.93, "首先判断你需不需要立刻转型"),
        ]
    )
    _assert_queue_strictly_monotonic(pane)
    pane._on_clean_cues_clicked()
    _assert_queue_strictly_monotonic(pane)

    # Step 4: Restart sequence -- fresh pane reopens the same source from persistence
    restart_pane = PathAMediaPane(tg_repo, db_path=db_path, available_languages=["zh"])
    with patch("glyphcue.ui.path_a_media_pane.probe_media") as mock_probe:
        mock_probe.return_value = MagicMock(width=1920, height=1080, duration_seconds=60.0, codec_name="h264")
        restart_pane.open_video(video_file)

    # Compare the three snapshots:
    # 1. Repository
    repo_cues = cue_repo.list_for_source(source_id)
    # 2. Workspace cues
    ws_cues = restart_pane.qa.cues
    # 3. QListWidget row items
    queue = restart_pane.qa.queue
    queue_cues = [restart_pane.qa.cue_id_for_row(r) for r in range(queue.count())]

    assert len(repo_cues) == len(ws_cues) == len(queue_cues)
    assert [c.id for c in repo_cues] == [c.id for c in ws_cues] == queue_cues
    _assert_queue_strictly_monotonic(restart_pane)

    # Assert no duplicate IDs exist
    assert len(set(queue_cues)) == len(queue_cues)
    # Assert timestamps strictly non-decreasing
    starts = [c.start_time for c in ws_cues]
    assert starts == sorted(starts)
