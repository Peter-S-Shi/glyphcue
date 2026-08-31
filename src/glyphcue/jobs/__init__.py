"""Cancelable background job orchestration.

Job runs its work on a background thread so it never blocks the Qt UI
thread. See ROADMAP.md Milestone 2.
"""

from glyphcue.jobs.job import Job, JobContext, JobState

__all__ = ["Job", "JobContext", "JobState"]
