from __future__ import annotations

_DEFAULT_TOLERANCE_SECONDS = 0.05


def qt_position_seconds_to_pyav_range(
    position_seconds: float, tolerance_seconds: float = _DEFAULT_TOLERANCE_SECONDS
) -> tuple[float, float]:
    """Map a Qt Multimedia playback position to the PyAvMediaFrameSource
    range that contains the analysis frame at that position.

    Human playback (Qt Multimedia) and algorithmic frame access (PyAV)
    are two independent decoders over the same file, but both already
    express time as absolute seconds on one shared source timeline --
    there is no frame-index/fps conversion between them. The only
    reason this function exists at all is to bound a small lookup
    window around the requested position (frame boundaries rarely land
    on an exact float), not to convert units.
    """
    start = max(0.0, position_seconds - tolerance_seconds)
    end = position_seconds + tolerance_seconds
    return start, end
