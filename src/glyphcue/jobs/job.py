from __future__ import annotations

import threading
from enum import Enum
from typing import Callable

from PySide6.QtCore import QObject, Signal


class JobState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    CANCEL_REQUESTED = "cancel_requested"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobContext:
    """Passed into a job's work function so it can cooperate with
    cancellation and report truthful progress."""

    def __init__(self, job: "Job") -> None:
        self._job = job

    def is_cancel_requested(self) -> bool:
        return self._job.state is JobState.CANCEL_REQUESTED

    def report_progress(
        self, phase: str, processed_seconds: float, total_seconds: float
    ) -> None:
        self._job.progress.emit(phase, processed_seconds, total_seconds)


class Job(QObject):
    """A cancelable background job that never runs on the calling thread.

    `work` receives a JobContext and must check
    `context.is_cancel_requested()` periodically to cooperate with
    cancellation. `start()` returns immediately; the work runs on a
    background thread, so it never blocks the Qt UI thread.
    """

    progress = Signal(str, float, float)
    state_changed = Signal(object)
    finished = Signal()

    def __init__(self, work: Callable[[JobContext], None]) -> None:
        super().__init__()
        self._work = work
        self._state = JobState.QUEUED
        self._thread: threading.Thread | None = None

    @property
    def state(self) -> JobState:
        return self._state

    def _set_state(self, new_state: JobState) -> None:
        self._state = new_state
        self.state_changed.emit(new_state)

    def start(self) -> None:
        self._set_state(JobState.RUNNING)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def request_cancel(self) -> None:
        if self._state in (JobState.QUEUED, JobState.RUNNING):
            self._set_state(JobState.CANCEL_REQUESTED)

    def wait(self, timeout: float | None = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout)

    def _run(self) -> None:
        context = JobContext(self)
        try:
            self._work(context)
        except Exception:
            self._set_state(JobState.FAILED)
        else:
            if self._state is JobState.CANCEL_REQUESTED:
                self._set_state(JobState.CANCELLED)
            else:
                self._set_state(JobState.SUCCEEDED)
        finally:
            self.finished.emit()
