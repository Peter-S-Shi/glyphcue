import threading
import time

from PySide6.QtCore import QEventLoop, QTimer

from glyphcue.jobs.job import Job, JobState


class _FinishedWaiter:
    """Arms a wait for `job.finished` before the job can possibly emit it.

    Job signals are emitted from a background thread and queued for
    delivery on the thread that owns the Job (the caller's thread), so
    observing them (progress, state_changed) requires the event loop to
    actually run -- a bare thread `.join()` only proves the work finished,
    not that its signals were delivered. The connection must be made
    before the job starts: connecting afterwards can race a job that
    finishes (and emits `finished`) before the connection exists, which
    would otherwise stall until the timeout fallback.
    """

    def __init__(self, job: Job, timeout: float = 2.0) -> None:
        self._job = job
        self._loop = QEventLoop()
        job.finished.connect(self._loop.quit)
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._loop.quit)
        self._timer.start(int(timeout * 1000))

    def wait(self) -> None:
        self._loop.exec()
        self._job.wait(timeout=0.5)


def _run_to_completion(job: Job, timeout: float = 2.0) -> None:
    waiter = _FinishedWaiter(job, timeout)
    job.start()
    waiter.wait()


def test_starting_a_job_transitions_it_to_running(qapp_guard):
    release = threading.Event()
    job = Job(work=lambda ctx: release.wait(timeout=2))

    job.start()
    try:
        assert job.state is JobState.RUNNING
    finally:
        release.set()
        job.wait(timeout=2)


def test_a_job_whose_work_completes_reaches_succeeded(qapp_guard):
    job = Job(work=lambda ctx: None)

    _run_to_completion(job)

    assert job.state is JobState.SUCCEEDED


def test_a_job_whose_work_raises_reaches_failed(qapp_guard):
    def failing_work(ctx):
        raise ValueError("boom")

    job = Job(work=failing_work)

    _run_to_completion(job)

    assert job.state is JobState.FAILED


def test_job_reports_truthful_phase_and_processed_time_progress(qapp_guard):
    reported = []

    def work(ctx):
        ctx.report_progress("decoding", 1.0, 4.0)
        ctx.report_progress("decoding", 2.0, 4.0)

    job = Job(work=work)
    job.progress.connect(lambda phase, processed, total: reported.append((phase, processed, total)))

    _run_to_completion(job)

    assert reported == [("decoding", 1.0, 4.0), ("decoding", 2.0, 4.0)]


def test_a_cancel_requested_job_stops_early_and_reaches_cancelled(qapp_guard):
    completed_iterations = []

    def work(ctx):
        for i in range(20):
            if ctx.is_cancel_requested():
                return
            completed_iterations.append(i)
            time.sleep(0.01)

    job = Job(work=work)
    waiter = _FinishedWaiter(job)
    job.start()
    time.sleep(0.03)  # let a few iterations run first
    job.request_cancel()
    waiter.wait()

    assert job.state is JobState.CANCELLED
    assert len(completed_iterations) < 20


def test_starting_a_job_returns_immediately_without_blocking_the_caller(qapp_guard):
    job = Job(work=lambda ctx: time.sleep(0.3))

    started_at = time.monotonic()
    job.start()
    elapsed = time.monotonic() - started_at

    assert elapsed < 0.05
    job.wait(timeout=2)


def test_ui_thread_stays_responsive_while_a_job_runs(qapp_guard):
    from PySide6.QtWidgets import QApplication

    job = Job(work=lambda ctx: time.sleep(0.3))
    job.start()

    # If the job were blocking the calling (UI) thread, pumping the event
    # loop repeatedly would take roughly as long as the job itself. Since
    # the job runs on a background thread, these calls should return
    # almost instantly even while the job is still in progress.
    started_at = time.monotonic()
    for _ in range(20):
        QApplication.processEvents()
    elapsed = time.monotonic() - started_at

    assert elapsed < 0.15
    job.wait(timeout=2)
