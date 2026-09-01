"""Regression for the M10 private-corpus incident
(docs/m10_private_corpus_incident.md): a job that never reaches a
terminal state -- even after cooperative cancellation is requested --
must abort the whole evaluation run, not be silently abandoned while the
caller starts the next entry's job on an orphaned background thread.
"""

import threading

import pytest

from glyphcue.jobs.job import Job

from benchmarks._job_harness import EvaluationJobDidNotTerminateError, run_job_or_cancel


def _non_cooperative_work(context) -> None:
    # Deliberately ignores context.is_cancel_requested() -- models a job
    # that will not terminate even once cancellation is requested.
    forever = threading.Event()
    forever.wait()


def test_a_non_terminating_job_aborts_the_run_before_the_next_entry_can_start(qapp_guard):
    first_job = Job(work=_non_cooperative_work)
    second_job_started = threading.Event()
    second_job = Job(work=lambda context: second_job_started.set())

    def _run_sequential_entries() -> None:
        for job in (first_job, second_job):
            run_job_or_cancel(job, timeout_seconds=0.05, cancel_grace_seconds=0.05)

    with pytest.raises(EvaluationJobDidNotTerminateError):
        _run_sequential_entries()

    assert not second_job_started.is_set()
