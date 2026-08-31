from __future__ import annotations

import sqlite3

from glyphcue.domain.roi import ROI
from glyphcue.domain.track_group import TrackGroup

_LANGUAGE_SEPARATOR = "\x1f"


class TrackGroupRepository:
    """SQLite-backed repository boundary for TrackGroup aggregates."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def add(self, track_group: TrackGroup) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO track_groups "
                "(id, roi_x, roi_y, roi_width, roi_height, languages) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    track_group.id,
                    track_group.roi.x,
                    track_group.roi.y,
                    track_group.roi.width,
                    track_group.roi.height,
                    _LANGUAGE_SEPARATOR.join(track_group.languages),
                ),
            )

    def save(self, track_group: TrackGroup) -> None:
        """Insert or, if `track_group.id` already exists, update it.

        This is the seam a UI redefining a Track Group's ROI should use:
        re-saving the same id updates it in place rather than raising a
        primary-key error.
        """
        with self._conn:
            self._conn.execute(
                "INSERT INTO track_groups "
                "(id, roi_x, roi_y, roi_width, roi_height, languages) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET "
                "roi_x = excluded.roi_x, "
                "roi_y = excluded.roi_y, "
                "roi_width = excluded.roi_width, "
                "roi_height = excluded.roi_height, "
                "languages = excluded.languages",
                (
                    track_group.id,
                    track_group.roi.x,
                    track_group.roi.y,
                    track_group.roi.width,
                    track_group.roi.height,
                    _LANGUAGE_SEPARATOR.join(track_group.languages),
                ),
            )

    def get(self, track_group_id: str) -> TrackGroup | None:
        row = self._conn.execute(
            "SELECT id, roi_x, roi_y, roi_width, roi_height, languages "
            "FROM track_groups WHERE id = ?",
            (track_group_id,),
        ).fetchone()
        if row is None:
            return None
        return self._build_track_group(row)

    def list_all(self) -> list[TrackGroup]:
        rows = self._conn.execute(
            "SELECT id, roi_x, roi_y, roi_width, roi_height, languages "
            "FROM track_groups ORDER BY id"
        ).fetchall()
        return [self._build_track_group(row) for row in rows]

    def _build_track_group(self, row: tuple) -> TrackGroup:
        track_group_id, roi_x, roi_y, roi_width, roi_height, languages = row
        return TrackGroup(
            id=track_group_id,
            roi=ROI(x=roi_x, y=roi_y, width=roi_width, height=roi_height),
            languages=tuple(languages.split(_LANGUAGE_SEPARATOR)),
        )
