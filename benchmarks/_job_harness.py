"""Shared cooperative-cancellation job runner for M10 evaluation harnesses.

Extracted after `benchmarks/private_video_corpus/run_evaluation.py`'s
original `_run_job` caused a real ~40-minute crash
(`docs/m10_private_corpus_incident.md`): its timeout path quit only the
local Qt event loop, never called `job.request_cancel()`, so an
overrunning job's background thread kept running, orphaned, while the
caller moved on to start the *next* entry's job -- turning an intended
sequential run into unbounded concurrent execution.

The contract here is stricter than "try to cancel": `run_job_or_cancel`
must never return to its caller while the job's worker thread may still
be alive. If cooperative cancellation is requested but the job does not
reach a terminal state (`succeeded` / `failed` / `cancelled`) within the
bounded grace period, this raises `EvaluationJobDidNotTerminateError`
instead of returning a state string -- the caller's sequential run loop
must let that propagate and abort the whole run rather than constructing
or starting the next entry/fixture. No unsafe Python thread termination
is attempted anywhere here; a job that truly will not cooperate is a
fatal condition for the run, not something to force-kill.
"""

from __future__ import annotations

from PySide6.QtCore import QEventLoop, QTimer

_TERMINAL_STATES = {"succeeded", "failed", "cancelled"}


class EvaluationJobDidNotTerminateError(RuntimeError):
    """A job neither finished nor reached a terminal state after
    cooperative cancellation was requested and given its grace period.
    The run this job belongs to must abort rather than continue to the
    next entry/fixture while the worker thread may still be alive."""


def run_job_or_cancel(job, *, timeout_seconds: float, cancel_grace_seconds: float = 30.0) -> str:
    """Start `job`, wait up to `timeout_seconds`, and if it is still
    running, request cancellation and wait up to `cancel_grace_seconds`
    more for it to actually stop. Returns the job's real terminal state
    name. Raises `EvaluationJobDidNotTerminateError` -- never returns --
    if the job has not reached a terminal state by the end of the grace
    period."""
    progress_log: list[tuple[str, float, float]] = []
    job.progress.connect(lambda phase, done, total: progress_log.append((phase, done, total)))

    loop = QEventLoop()
    job.finished.connect(loop.quit)
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(int(timeout_seconds * 1000))
    job.start()
    loop.exec()

    if job.state.value == "running":
        print(f"  [!] job exceeded {timeout_seconds}s -- requesting real cancellation, not abandoning it")
        job.request_cancel()
        cancel_loop = QEventLoop()
        job.finished.connect(cancel_loop.quit)
        cancel_timer = QTimer()
        cancel_timer.setSingleShot(True)
        cancel_timer.timeout.connect(cancel_loop.quit)
        cancel_timer.start(int(cancel_grace_seconds * 1000))
        cancel_loop.exec()

    job.wait(timeout=5.0)
    if progress_log:
        last_phase, last_done, last_total = progress_log[-1]
        print(f"  progress: {len(progress_log)} updates, last={last_phase} {last_done:.2f}/{last_total:.2f}s")

    final_state = job.state.value
    if final_state not in _TERMINAL_STATES:
        raise EvaluationJobDidNotTerminateError(
            f"job did not reach a terminal state within {cancel_grace_seconds}s of "
            f"requesting cancellation (state={final_state!r}); aborting the evaluation "
            "run rather than starting the next entry while this worker thread may "
            "still be alive (see docs/m10_private_corpus_incident.md)"
        )
    return final_state
