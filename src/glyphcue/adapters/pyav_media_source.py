from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import av
import numpy as np

_MICROSECONDS_PER_SECOND = 1_000_000


@dataclass(frozen=True)
class MediaMetadata:
    """Stream-inspection result for a local media file."""

    duration_seconds: float
    width: int
    height: int
    codec_name: str


def probe_media(path: Path) -> MediaMetadata:
    """Inspect a local video file without decoding its frames."""
    container = av.open(str(path))
    try:
        stream = container.streams.video[0]
        duration_seconds = (container.duration or 0) / _MICROSECONDS_PER_SECOND
        return MediaMetadata(
            duration_seconds=duration_seconds,
            width=stream.width,
            height=stream.height,
            codec_name=stream.codec_context.name,
        )
    finally:
        container.close()


class PyAvMediaFrameSource:
    """Concrete MediaFrameSource backed by PyAV, for algorithmic frame
    access (analysis decoding), independent of Qt Multimedia playback.

    Timestamps come from each decoded frame's real presentation timestamp
    (PTS), converted via the stream's time_base -- never from
    `frame_index / fps`, which is not a valid universal time model (see
    tests/adapters/test_pyav_media_source.py for a fixture proving this).
    """

    def __init__(self) -> None:
        self._container: av.container.InputContainer | None = None
        self._stream = None

    def open(self, path: Path) -> None:
        self._container = av.open(str(path))
        self._stream = self._container.streams.video[0]

    def frames(self, start_time: float, end_time: float) -> Iterator[tuple[float, np.ndarray]]:
        if self._container is None or self._stream is None:
            raise RuntimeError("PyAvMediaFrameSource.open() must be called first")

        offset = int(start_time / self._stream.time_base)
        self._container.seek(offset, stream=self._stream)

        for frame in self._container.decode(self._stream):
            timestamp = float(frame.pts * self._stream.time_base)
            if timestamp < start_time:
                continue
            if timestamp >= end_time:
                break
            yield timestamp, frame.to_ndarray(format="rgb24")

    def close(self) -> None:
        if self._container is not None:
            self._container.close()
            self._container = None
            self._stream = None
