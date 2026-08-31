from __future__ import annotations

from pathlib import Path

from glyphcue.adapters.pyav_media_source import PyAvMediaFrameSource, probe_media
from glyphcue.application.processing_range import ProcessingRange
from glyphcue.jobs.job import Job, JobContext


def build_media_analysis_job(path: Path, processing_range: ProcessingRange) -> Job:
    """A cancelable background job that decodes frames from `path` for
    analysis, over `processing_range`.

    No OCR runs here (Milestone 2 scope): this proves the media/job
    orchestration foundation -- selective/OCR evidence extraction is
    Milestone 4. Owns the PyAvMediaFrameSource's lifecycle itself so the
    decoding resource is opened and closed on the job's own thread.
    """

    def work(context: JobContext) -> None:
        metadata = probe_media(path)
        start, end = processing_range.resolve(metadata.duration_seconds)

        source = PyAvMediaFrameSource()
        source.open(path)
        try:
            for timestamp, _frame in source.frames(start, end):
                if context.is_cancel_requested():
                    return
                context.report_progress("decoding", timestamp, metadata.duration_seconds)
        finally:
            source.close()

    return Job(work=work)
