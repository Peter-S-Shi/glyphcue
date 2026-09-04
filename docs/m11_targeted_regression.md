# Milestone 11 — Targeted Regression (stage ④)

**Scope:** a narrow, evidence-driven regression over the high-risk seams
this round's Corrective Hardening and Experimental Hybrid integration
actually touched. Baseline: `milestone/11-product-hardening-full-regression`.

**This is not the M11 Full Regression, and it is not merge-readiness.**
No OCR research question was reopened, no threshold was retuned, the
legacy Production path was not removed, and the Experimental Hybrid
profile is still opt-in developer/manual-QA-only — it was not promoted.

Every row below is backed by an automated test that runs in CI, not by
inspection. Three new test modules carry the evidence:

- `tests/ui/test_m11_targeted_regression_workspace_seams.py` (23 tests)
- `tests/ui/test_m11_targeted_regression_playback_seams.py` (4 tests)
- `tests/ui/test_m11_targeted_regression_layout_seams.py` (2 tests + 1 recorded `xfail`)

---

## Seam results

| # | Seam | Result | Evidence |
|---|------|--------|----------|
| 1 | Production / Experimental Hybrid profile isolation | **PASS** | A detector handed to `build_evidence_job_for_profile` is never called on the production profile (`detect_calls == 0`); a Hybrid run followed by a Production run in one pane produces a distinct `evidence_run_id`, re-initializes nothing, leaves `_active_hybrid_detector is None`, and shows only its own run's observations. |
| 2 | ROI persistence; the original ROI is not silently modified | **PASS** (one recorded residual) | A completed run leaves the ROI inputs byte-identical; a saved ROI round-trips a reopen unchanged; a second video does not inherit the first's ROI and the first's saved ROI is untouched. Residual below. |
| 3 | Processing Range boundaries vs. the source timeline | **PASS** | A run limited to 0.2–0.4s yields Cues timed 0.2s onward in absolute source seconds — never renumbered from zero. The range controls cannot be pushed past the real probed media duration. |
| 4 | A-B Preview Loop and Processing Range are independent | **PASS** | Changing the range leaves the loop enabled and unchanged; enabling and playing the loop leaves `current_processing_range()` identical. |
| 5 | A-B Loop ↔ Cue Replay takeover / restore | **FAIL → FIXED** | See "Defect 1". |
| 6 | Discard Latest OCR Run after a Hybrid run | **PASS** | After a real Experimental Hybrid run through the pane, Discard restores the pre-run workspace, clears the evidence pane, and disables itself again. |
| 7 | Non-destructive merge across repeated / overlapping runs | **PASS** | An Approved Cue and a hand-edited (`NEEDS_REVIEW`) Cue both survive a second run over the same range, the edit's text intact. |
| 8 | Multiple machine observations do not create duplicate user-facing Cues | **PASS** | A repeated run does not grow the Cue count and produces no duplicate Cue identity; a second, wider overlapping run produces no duplicate Cue span. |
| 9 | Review Priority ordering does not pollute playback temporal ordering | **PASS** | The queue is priority-ordered (High first) while `qa.cues` — what playback, the compact timeline and export all read — stays strictly temporal. |
| 10 | High / Pending Cue behavior | **PASS** | A high-priority machine Cue reads `[High]` + `○ Pending`, and its `review_state` stays `PENDING`: a priority level is never mistaken for a human decision. |
| 11 | Source / video switching cleanup | **PASS** | Switching video clears Cues, the A-B loop, the Discard availability and the progress bar, and rebinds `_source_id`; reopening the first video brings back exactly its own Cues. |
| 12 | Path A / Path B isolation | **PASS** | Opening a caption file switches modes; the two workspaces' Cue id sets are disjoint, and switching back leaves Path A's Cues exactly as they were. |
| 13 | Progress / Cancel / diagnostic report | **PASS** | A successful run completes the progress bar and reports realtime ratio, frames, OCR calls, observations and new-Cue counts; a cancelled run reports the cancellation and leaves Discard unavailable; the diagnostic report actions unlock only after a dry run. |
| 14 | Narrow-window: ROI hint and OCR Evidence Pipeline bottom controls | **FAIL → FIXED** (one residual recorded) | See "Defect 2". |

---

## Defect 1 — a hand-paused Cue Replay left the A-B loop suspended forever

**Seam:** `PlaybackController.play_span` / `pause`.

`play_span` suspended an active A-B preview loop and restored it only on
the "span ran to its own end" path
(`_on_position_changed_during_span`). A user who paused mid-replay — the
ordinary way to stop listening to a Cue — never reached that path, so:

- `is_loop_enabled` stayed `False` with no way back short of re-arming
  the loop by hand, and
- the abandoned span stayed armed, which additionally suppressed the
  loop's own wrap-around (`_on_playback_position_changed` is gated on no
  span being active) and would pause playback again later, whenever the
  playhead happened to cross the dead span's end.

This is exactly the "Cue Replay 中途人工 Pause 后 loop 恢复异常" risk
carried into this stage; it reproduces deterministically.

**Fix:** `pause()` now finalizes any in-flight span through a single
idempotent `_finish_span()` — disconnect, clear the span, hand the loop
back — and `_on_position_changed_during_span` simply calls `pause()`.
One exit path instead of two, so "the replay ended" cannot mean two
different things.

`play_span` additionally no longer stacks a second connection on the
same slot when a replay is re-targeted at another Cue mid-replay.

**Pinpoint verification:** the two red tests in
`test_m11_targeted_regression_playback_seams.py` now pass; the existing
happy-path restore test and all 8 `test_playback_controller.py` tests
still pass.

## Defect 2 — "Discard Latest OCR Run" was invisible at the app's default window size

**Seam:** the shown `GlyphCueWorkbench` at real window sizes.

The four OCR Evidence Pipeline controls sat in one `QHBoxLayout` whose
combined minimum width is 834px, inside a center pane whose scroll area
has horizontal scrolling switched off on purpose
(`ScrollBarAlwaysOff`, pinned by
`test_preview_ab_loop_and_playhead_range_actions.py`). With no
horizontal scrollbar, the overflow is not scrolled to — it is gone.
Measured, before the fix:

| Window | ROI hint clipped | OCR controls fully invisible |
|---|---|---|
| 1024×600 (workbench minimum) | yes | Cancel OCR, Discard Latest OCR Run |
| **1280×720 (the size the app opens at)** | no | **Discard Latest OCR Run** |
| 1600×900 | no | none |
| 1920×1080 | no | none |

The affected control is the one this round added, and it reported
`isVisible() == True` with a sane geometry the whole time — only
`visibleRegion().isEmpty()` exposed it.

**Fix:** the four controls are laid out 2×2 (`QGridLayout`) instead of
1×4, bringing the row's minimum width under the center pane's real
width. No button was renamed, removed or restyled.

**Pinpoint verification:** both layout tests pass at 1280×720; every
other UI test file still passes, including the visual-hierarchy and
responsive-layout suites.

---

## Recorded findings — reproduced, deliberately NOT fixed in this pass

1. **Whole-workbench content overflows at the 1024×600 minimum window
   size.** Wider than the OCR row: `previewLoopBox` alone needs ~938px
   against a ~392px viewport, `performanceDiagnosticsBox` ~618px, and
   Path A's left `structureCard` ~676px against a ~247px viewport.
   Predates this round's corrective hardening, and fixing it is a
   responsive-layout pass across three panes, not a targeted regression
   fix. Recorded as a `strict=True` `xfail` in
   `test_m11_targeted_regression_layout_seams.py` so it stays visible
   and the marker fails loudly the moment it is fixed.

2. **A hand-drawn ROI is quantized before it runs.** The ROI spin boxes
   have carried 3 decimals since M2 while `ROI`/`current_roi()` carry 4,
   so the ROI that runs can sit up to 0.0005 (sub-pixel to ~1px on a
   1920-wide frame) from the rectangle drawn on the video. Not a
   regression from this round. Pinned by a bound assertion so the gap
   cannot silently widen.

3. **Two `pytest` processes running Qt tests at the same time block each
   other** (0% CPU on both, no progress). Observed twice while gathering
   this evidence, and both times it was self-inflicted: a background run
   left going while another started. Run alone the suite is healthy —
   `pytest` completes in 112s. Worth knowing before M11's Full Regression
   is scheduled alongside anything else; not a product defect, and
   nothing to fix in the code.

---

## Test results

| Suite | Result |
|---|---|
| **`pytest` (whole repository, run alone)** | **831 passed, 1 xfailed, 112s** |
| `tests/application tests/adapters tests/persistence tests/jobs tests/evaluation tests/domain tests/benchmarks` | 540 passed |
| `tests/ui` (one process) | 291 passed, 1 xfailed |
| `tests/ui`, also run per file (33 files) | all passed, 0 failed |

## Still needing a human gate

- Real-video confirmation that a hand-paused Cue Replay now hands the
  A-B loop back the way it feels like it should (automated evidence
  covers the state machine, not the felt behavior).
- Visual sign-off on the 2×2 OCR control grid.
- Everything M11's own acceptance gate still carries and this stage did
  not touch: the transferred representative-video evaluation (ROADMAP
  §17/§18 gate 9), packaging hardening, formal Manual QA, and the Full
  Regression itself.
