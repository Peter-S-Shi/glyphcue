from __future__ import annotations

from pathlib import Path
from typing import Iterator, Protocol


class MediaFrameSource(Protocol):
    """Boundary for algorithmic, PTS-correct frame access (e.g. PyAV).

    Implementations own the third-party decoding library entirely
    internally. This is distinct from human playback, which is a separate
    concern (Qt Multimedia) not covered by this contract.
    """

    def open(self, path: Path) -> None:
        """Open a local media file for frame-accurate decoding."""
        ...

    def frames(self, start_time: float, end_time: float) -> Iterator[tuple[float, object]]:
        """Yield (timestamp_seconds, frame) pairs for the given time range."""
        ...

    def close(self) -> None:
        """Release decoding resources."""
        ...
