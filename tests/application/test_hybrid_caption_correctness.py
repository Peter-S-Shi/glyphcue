"""End-to-end synthetic caption identity and time coverage contracts.

Only external OCR/detection are scripted. Real video decoding, Hybrid job,
state grouping, persistence and public Cue reconstruction run unchanged.
"""
from fractions import Fraction

import av
import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from glyphcue.adapters.ocr_types import OcrRuntimeInfo, OcrTextRegion
from glyphcue.application.consensus_reconstruction import reconstruct_cues_with_consensus
from glyphcue.application.hybrid_evidence_job import build_hybrid_ocr_evidence_job
from glyphcue.application.pipeline_metrics import PipelineMetrics
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.domain.roi import ROI
from glyphcue.domain.caption_identity import caption_identity_evidence
from glyphcue.application.review_priority import (
    compute_review_priority, review_signals_from_consensus_diagnostics,
)
from glyphcue.jobs.job import JobState
from glyphcue.persistence.database import connect
from glyphcue.persistence.observation_repository import ObservationRepository

CAPTIONS = ('Travel north today', 'Turn south tomorrow', 'Wait east tonight')
ALTERNATIVES = ('Walk west today', 'Stay home tomorrow', 'Leave south tonight')
TABLE = 'Fixed planning table: owner action date status'
WIDTH, HEIGHT = 640, 144


def polygon(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def make_video(path, *, table, timing=False, upper_caption=False, multiline=False, ambiguous=False, sequence='abc', singleton_blocks=False, inverted_roles=False, third_line=False):
    with av.open(str(path), 'w') as container:
        stream = container.add_stream('ffv1', rate=10)
        stream.width, stream.height, stream.pix_fmt = WIDTH, HEIGHT, 'bgr0'
        for index in range(60):
            state = index // (30 if timing else 20)
            if sequence == 'aba' and state == 2:
                state = 0
            if sequence == 'hidden':
                state = int(10 <= index <= 12)
            image = Image.new('RGB', (WIDTH, HEIGHT), 'white')
            draw = ImageDraw.Draw(image)
            draw.rectangle((0, 0, 7, 7), fill=(40 + state * 80,) * 3)
            y = 12 if upper_caption or ambiguous else 75
            if table:
                table_y = 90 if upper_caption else 12
                draw.text((15, table_y), TABLE, font=ImageFont.load_default(size=14), fill='black')
                draw.text((15, table_y + 18), 'Row one     Row two     Row three', font=ImageFont.load_default(size=14), fill='black')
            rendered = CAPTIONS[0] if inverted_roles else CAPTIONS[state]
            # A mild initial glyph defect, not a real caption change. The
            # repeated clean image later in the state is the visual medoid.
            draw.text((80, y), rendered, font=ImageFont.load_default(size=24), fill='black')
            if timing and index % 30 < 4:
                draw.rectangle((100, y + 10, 101, y + 14), fill='black')
            if multiline:
                draw.text((80, y + 28), 'Keep this second line', font=ImageFont.load_default(size=24), fill='black')
            if third_line:
                draw.text((80, y + 58), 'Retain this third line', font=ImageFont.load_default(size=24), fill='black')
            if ambiguous:
                draw.text((80, 90), ALTERNATIVES[state], font=ImageFont.load_default(size=24), fill='black')
                if not singleton_blocks:
                    draw.text((80, 118), 'Another second line', font=ImageFont.load_default(size=24), fill='black')
            frame = av.VideoFrame.from_ndarray(np.array(image), format='rgb24')
            frame.pts, frame.time_base = index, Fraction(1, 10)
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)


class ScriptedText:
    """External OCR/localization boundary: deterministic exact synthetic text."""
    def __init__(self, *, table=True, upper_caption=False, multiline=False, ambiguous=False, singleton_blocks=False, inverted_roles=False):
        self.table, self.upper, self.multiline = table, upper_caption, multiline
        self.ambiguous = ambiguous
        self.singleton_blocks = singleton_blocks
        self.inverted_roles = inverted_roles

    def initialize(self): pass
    def shutdown(self): pass
    def runtime_info(self):
        return OcrRuntimeInfo('synthetic', '1', 'test', '1')

    def regions(self, image):
        state = int(round((float(image[:6, :6].mean()) - 40) / 80))
        y = 12 if self.upper or self.ambiguous else 75
        values = [OcrTextRegion(CAPTIONS[0] if self.inverted_roles else CAPTIONS[state], 0.99, 'en', polygon(80, y, 380, y + 24))]
        if self.multiline:
            values.append(OcrTextRegion('Keep this second line', 0.99, 'en', polygon(80, y + 28, 380, y + 52)))
        if self.ambiguous:
            values.append(OcrTextRegion(ALTERNATIVES[state], 0.99, 'en', polygon(80, 90, 380, 114)))
            if not self.singleton_blocks:
                values.append(OcrTextRegion('Another second line', 0.99, 'en', polygon(80, 118, 380, 142)))
        if self.table:
            ty = 90 if self.upper else 12
            values.extend([OcrTextRegion(TABLE, 0.99, 'en', polygon(15, ty, 620, ty + 14)),
                           OcrTextRegion('Row one Row two Row three', 0.99, 'en', polygon(15, ty + 18, 590, ty + 32))])
        return values

    def recognize(self, image): return self.regions(image)
    def detect(self, image): return [r.geometry for r in self.regions(image)]


def run_pipeline(tmp_path, *, table=True, timing=False, upper_caption=False, multiline=False, ambiguous=False, diagnostics=False, budget=64, sequence='abc', external=None, expected_state=JobState.SUCCEEDED, singleton_blocks=False, inverted_roles=False, third_line=False):
    video = tmp_path / 'synthetic.mkv'
    make_video(video, table=table, timing=timing, upper_caption=upper_caption, multiline=multiline, ambiguous=ambiguous, sequence=sequence, singleton_blocks=singleton_blocks, inverted_roles=inverted_roles, third_line=third_line)
    external = external or ScriptedText(table=table, upper_caption=upper_caption, multiline=multiline, ambiguous=ambiguous, singleton_blocks=singleton_blocks, inverted_roles=inverted_roles)
    db = tmp_path / 'evidence.sqlite3'
    job = build_hybrid_ocr_evidence_job(video, ProcessingRange(0, 5.9), ROI(0, 0, 1, 1),
                                      external, db, PipelineMetrics(), 'synthetic-run', detect=external.detect,
                                      caption_probe_budget=budget)
    external.job = job
    job.start(); job.wait(20)
    assert job.state is expected_state
    conn = connect(db)
    try:
        observations = ObservationRepository(conn).list_for_run('synthetic-run')
    finally:
        conn.close()
    cues, details = reconstruct_cues_with_consensus(observations, processing_end_time=5.9)
    if diagnostics:
        return observations, cues, details
    return observations, cues


def covering_text(cues, timestamp):
    return [c.language_layers[0].text for c in cues if c.start_time <= timestamp < c.end_time]


def test_successive_captions_inside_one_visual_state_keep_their_identity(tmp_path):
    observations, cues = run_pipeline(tmp_path)
    # Text may only cover its actual probe support. Unknown gaps are review
    # items, not a licence to interpolate a caption across a coarse envelope.
    evidence = [e for o in observations if (e := caption_identity_evidence(o)) is not None]
    assert len(evidence) == 1
    assert set(CAPTIONS) <= {b.text for p in evidence[0].probes for b in p.alternatives}
    assert [next(text for text in i.alternatives if text in CAPTIONS) for i in evidence[0].identities] == list(CAPTIONS)
    for observation in observations:
        if observation.text in CAPTIONS:
            assert covering_text(cues, observation.start_time) == ['']
    for t, caption in zip((1.0, 3.0, 5.0), CAPTIONS):
        assert all(text in ('', caption) for text in covering_text(cues, t))


def test_returning_caption_does_not_hide_the_middle_identity(tmp_path):
    observations, cues = run_pipeline(tmp_path, sequence='aba', budget=7)
    evidence = [e for o in observations if (e := caption_identity_evidence(o)) is not None]
    assert len(evidence) == 1, 'fixture must use one frozen coarse envelope'
    assert [next(text for text in i.alternatives if text in CAPTIONS) for i in evidence[0].identities] == [CAPTIONS[0], CAPTIONS[1], CAPTIONS[0]]
    assert evidence[0].boundary_brackets
    for probe in evidence[0].probes:
        assert covering_text(cues, probe.pts) == [probe.selected_text or '']


def test_medoid_pts_does_not_delay_the_observed_caption_span(tmp_path):
    observations, cues = run_pipeline(tmp_path, table=False, timing=True)
    # The real visual medoid can be later than the first observation. A
    # verified instant before that medoid still belongs to this caption.
    envelopes = [e for o in observations if (e := caption_identity_evidence(o)) is not None]
    assert any(e.envelope.representative_pts > e.envelope.observed_start for e in envelopes)
    for evidence in envelopes:
        envelope = evidence.envelope
        assert envelope.observed_start <= envelope.representative_pts <= envelope.observed_end
        assert envelope.observations[0].pts == envelope.observed_start
        assert envelope.observations[-1].pts == envelope.observed_end
        assert {envelope.observed_start, envelope.observed_end, envelope.representative_pts} <= {p.pts for p in evidence.probes}
        for probe in evidence.probes:
            assert covering_text(cues, probe.pts) == [probe.selected_text]
            for region_id in probe.raw_region_ids:
                observation = next(o for o in observations if o.id == region_id)
                assert observation.start_time == probe.pts
                assert observation.frame_reference.endswith(f'@{probe.pts:.6f}s')
    assert covering_text(cues, 3.1) == [CAPTIONS[1]]
    assert CAPTIONS[0] not in covering_text(cues, 3.1)


@pytest.mark.parametrize('upper_caption', [False, True])
def test_competing_table_does_not_enter_multiline_caption_identity(tmp_path, upper_caption):
    observations, cues = run_pipeline(tmp_path, upper_caption=upper_caption, multiline=True)
    assert TABLE in {o.text for o in observations}, 'raw non-caption evidence must remain retrievable'
    expected = {caption + '\nKeep this second line' for caption in CAPTIONS}
    evidence = [e for o in observations if (e := caption_identity_evidence(o)) is not None]
    assert expected <= {b.text for e in evidence for p in e.probes for b in p.alternatives}
    assert all(c.language_layers[0].text == '' for c in cues)
    for observation in observations:
        if observation.text in CAPTIONS:
            probe = next(p for e in evidence for p in e.probes if p.pts == observation.start_time)
            caption = next(b for b in probe.alternatives if observation.text in b.text)
            assert caption.text == observation.text + '\nKeep this second line'
            assert len(caption.region_ids) == 2


def test_equally_plausible_blocks_keep_ambiguity_instead_of_concatenation(tmp_path):
    observations, cues, diagnostics = run_pipeline(
        tmp_path, table=False, multiline=True, ambiguous=True, diagnostics=True,
    )
    raw_texts = {o.text for o in observations}
    assert set(CAPTIONS + ALTERNATIVES) <= raw_texts
    assert all(c.language_layers[0].text == '' for c in cues), 'no arbitrary winner'
    envelopes = [e for o in observations if (e := caption_identity_evidence(o)) is not None]
    for evidence in envelopes:
        for probe in evidence.probes:
            assert probe.selected_text is None
            assert len(probe.alternatives) == 2
            assert all(len(b.region_ids) == 2 for b in probe.alternatives)
            cue = next(c for c in cues if c.start_time <= probe.pts < c.end_time)
            diagnostic = next(d for d in diagnostics if d.cue_id == cue.id)
            assert diagnostic.caption_alternatives == tuple(b.text for b in probe.alternatives)
            priority = compute_review_priority(review_signals_from_consensus_diagnostics(diagnostic, observations))
            assert diagnostic.had_disagreement
            assert priority.score > 0


def test_hidden_return_remains_unresolved_when_budget_cannot_find_it(tmp_path):
    bounded = tmp_path / 'bounded'; bounded.mkdir()
    exhaustive = tmp_path / 'exhaustive'; exhaustive.mkdir()
    observations, cues, diagnostics = run_pipeline(bounded, sequence='hidden', budget=3, diagnostics=True)
    control, _ = run_pipeline(exhaustive, sequence='hidden', budget=64)
    assert CAPTIONS[1] in {o.text for o in control}, 'hidden change is on an existing detector observation'
    evidence = [e for o in observations if (e := caption_identity_evidence(o)) is not None]
    assert len(evidence) == 1
    assert not evidence[0].all_observations_probed
    assert evidence[0].stop_reason == 'budget_exhausted'
    hidden = [o.start_time for o in control if o.text == CAPTIONS[1]]
    assert any(all(p.pts != t for p in evidence[0].probes) for t in hidden)
    for t in hidden:
        if all(p.pts != t for p in evidence[0].probes):
            assert any(a < t < b for a, b in evidence[0].unqueried_intervals)
            assert covering_text(cues, t) == ['']
            cue = next(c for c in cues if c.start_time <= t < c.end_time)
            diagnostic = next(d for d in diagnostics if d.cue_id == cue.id)
            assert diagnostic.had_disagreement


class JitteredText(ScriptedText):
    def recognize(self, image):
        regions = super().recognize(image)
        offset = float(image[:6, :6].mean()) / 100
        return [OcrTextRegion(r.text, r.confidence, r.language,
                              tuple((x + offset, y + offset) for x, y in r.geometry)) for r in regions]


def test_geometry_jitter_preserves_complete_multiline_blocks(tmp_path):
    observations, cues = run_pipeline(tmp_path, multiline=True, external=JitteredText(multiline=True))
    evidence = [e for o in observations if (e := caption_identity_evidence(o)) is not None]
    assert not any(e.correspondence_ambiguous for e in evidence)
    assert {c + '\nKeep this second line' for c in CAPTIONS} <= {
        b.text for e in evidence for p in e.probes for b in p.alternatives}
    assert all(c.language_layers[0].text == '' for c in cues)


def test_a_unique_single_block_still_produces_probe_supported_text(tmp_path):
    observations, cues = run_pipeline(tmp_path, table=False)
    assert set(CAPTIONS) == {c.language_layers[0].text for c in cues if c.language_layers[0].text}
    for observation in observations:
        if observation.text:
            assert covering_text(cues, observation.start_time) == [observation.text]


class InterruptedText(ScriptedText):
    def __init__(self, fail=False):
        super().__init__()
        self.calls = 0
        self.stopped = False
        self.fail = fail

    def recognize(self, image):
        self.calls += 1
        if self.calls == 2:
            if self.fail:
                raise RuntimeError('synthetic OCR failure')
            self.job.request_cancel()
        return super().recognize(image)

    def shutdown(self):
        self.stopped = True


@pytest.mark.parametrize('fail', [False, True])
def test_interrupted_probing_preserves_raw_evidence_and_unresolved_envelope(tmp_path, fail):
    engine = InterruptedText(fail=fail)
    observations, cues, diagnostics = run_pipeline(
        tmp_path, external=engine, expected_state=JobState.FAILED if fail else JobState.CANCELLED,
        diagnostics=True,
    )
    assert engine.calls == 2 and engine.stopped
    assert any(o.text == CAPTIONS[0] for o in observations)
    evidence = [e for o in observations if (e := caption_identity_evidence(o)) is not None]
    assert len(evidence) == 1
    assert evidence[0].stop_reason == ('ocr_failed' if fail else 'cancelled')
    assert not evidence[0].all_observations_probed
    assert evidence[0].unqueried_intervals
    assert all(c.language_layers[0].text == '' for c in cues)
    assert all(d.had_disagreement for d in diagnostics)


def test_reopened_review_keeps_no_winner_alternatives_and_flags(tmp_path):
    from PySide6.QtWidgets import QApplication
    from glyphcue.application.source_identity import normalize_source_id
    from glyphcue.persistence.repository import CueRepository
    from glyphcue.persistence.track_group_repository import TrackGroupRepository
    from glyphcue.ui.path_a_media_pane import PathAMediaPane

    app = QApplication.instance() or QApplication([])
    observations, cues = run_pipeline(tmp_path, table=False, multiline=True, ambiguous=True)
    video = tmp_path / 'synthetic.mkv'
    db = tmp_path / 'evidence.sqlite3'
    conn = connect(db)
    CueRepository(conn).save_cues_for_source(normalize_source_id(video), cues)
    conn.close()
    conn = connect(db)
    pane = PathAMediaPane(TrackGroupRepository(conn), db_path=db)
    try:
        pane.open_video(video)
        app.processEvents()
        assert pane.qa.cues
        assert all(c.language_layers[0].text == '' for c in pane.qa.cues)
        assert pane.qa.diagnostics_view.toPlainText() != 'No Review Flags'
        assert 'Alternatives' in pane.qa.evidence_view.toPlainText()
        assert 'Keep this second line' in pane.qa.evidence_view.toPlainText()
        assert 'Another second line' in pane.qa.evidence_view.toPlainText()
    finally:
        pane.window.close()
        conn.close()


def test_two_single_line_blocks_cannot_be_selected_as_one_caption(tmp_path):
    observations, cues = run_pipeline(tmp_path, table=False, ambiguous=True, singleton_blocks=True)
    assert all(c.language_layers[0].text == '' for c in cues)
    for observation in observations:
        evidence = caption_identity_evidence(observation)
        if evidence:
            for probe in evidence.probes:
                assert probe.selected_text is None
                assert any(b.text in CAPTIONS for b in probe.alternatives)
                assert any(b.text in ALTERNATIVES for b in probe.alternatives)


def test_changing_dashboard_does_not_remove_static_multiline_caption(tmp_path):
    observations, cues = run_pipeline(tmp_path, table=False, multiline=True, ambiguous=True, inverted_roles=True)
    assert all(c.language_layers[0].text == '' for c in cues)
    for observation in observations:
        evidence = caption_identity_evidence(observation)
        if evidence:
            for probe in evidence.probes:
                assert probe.selected_text is None
                assert CAPTIONS[0] + '\nKeep this second line' in {b.text for b in probe.alternatives}
                assert any(b.text.endswith('\nAnother second line') for b in probe.alternatives)


def test_time_between_distinct_envelopes_is_reviewable_not_silently_absent(tmp_path):
    observations, cues, diagnostics = run_pipeline(tmp_path, table=False, timing=True, diagnostics=True)
    evidence = [e for o in observations if (e := caption_identity_evidence(o)) is not None]
    left, right = evidence[:2]
    assert left.envelope.observed_end < right.envelope.observed_start
    t = (left.envelope.observed_end + right.envelope.observed_start) / 2
    assert covering_text(cues, t) == ['']
    cue = next(c for c in cues if c.start_time <= t < c.end_time)
    diagnostic = next(d for d in diagnostics if d.cue_id == cue.id)
    assert diagnostic.had_disagreement


def test_inconsistent_persisted_selection_is_rejected_not_reconstructed(tmp_path):
    import json
    from dataclasses import replace
    from glyphcue.domain.caption_identity import PAYLOAD_KEY

    observations, _ = run_pipeline(tmp_path, table=False)
    marker = next(o for o in observations if caption_identity_evidence(o) is not None)
    payload = json.loads(marker.provenance.detail[PAYLOAD_KEY])
    payload['probes'][0]['selected_text'] = 'Invented text with no raw support'
    invalid = replace(marker, provenance=replace(marker.provenance, detail={
        **marker.provenance.detail, PAYLOAD_KEY: json.dumps(payload),
    }))
    conn = connect(tmp_path / 'invalid-copy.sqlite3')
    try:
        repository = ObservationRepository(conn)
        for observation in observations:
            repository.add(invalid if observation.id == marker.id else observation, 'invalid-copy')
        with pytest.raises(ValueError, match='selected text'):
            reconstruct_cues_with_consensus(repository.list_for_run('invalid-copy'))
    finally:
        conn.close()


class ThreeLineText(ScriptedText):
    def __init__(self):
        super().__init__(table=False, upper_caption=True, multiline=True)

    def regions(self, image):
        return super().regions(image) + [OcrTextRegion(
            'Retain this third line', 0.99, 'en', polygon(80, 70, 380, 94))]


def test_three_line_caption_with_unequal_gaps_retains_intact_alternative(tmp_path):
    observations, cues = run_pipeline(tmp_path, table=False, upper_caption=True,
                                     multiline=True, third_line=True, external=ThreeLineText())
    for observation in observations:
        evidence = caption_identity_evidence(observation)
        if evidence:
            for probe in evidence.probes:
                text = next(b.text for b in probe.blocks if any(c in b.text for c in CAPTIONS))
                first_line = next(c for c in CAPTIONS if c in text)
                assert first_line + '\nKeep this second line\nRetain this third line' in {b.text for b in probe.alternatives}
                assert probe.selected_text is None
    assert all(c.language_layers[0].text == '' for c in cues)
