from __future__ import annotations

from pathlib import Path
from typing import Protocol


class MediaTransformService(Protocol):
    """Boundary for heavy media transforms via a bundled FFmpeg CLI.

    Implementations own process invocation (e.g. QProcess + ffmpeg)
    entirely internally; callers never see subprocess/FFmpeg details.
    """

    def transcode(self, source: Path, destination: Path, options: dict) -> None:
        """Transform `source` into `destination` according to `options`."""
        ...
