from __future__ import annotations

import sqlite3

from glyphcue.domain.observation import Observation
from glyphcue.domain.provenance import Provenance, ProvenanceKind
from glyphcue.domain.roi import ROI

_PAIR_SEPARATOR = "\x1f"
_POINT_SEPARATOR = "\x1e"


def _encode_detail(detail) -> str:
    return _PAIR_SEPARATOR.join(f"{key}={value}" for key, value in detail.items())


def _decode_detail(encoded: str) -> dict[str, str]:
    if not encoded:
        return {}
    pairs = (pair.split("=", 1) for pair in encoded.split(_PAIR_SEPARATOR))
    return {key: value for key, value in pairs}


def _encode_geometry(geometry) -> str | None:
    if geometry is None:
        return None
    return _PAIR_SEPARATOR.join(f"{x},{y}" for x, y in geometry)


def _decode_geometry(encoded: str | None) -> tuple[tuple[float, float], ...] | None:
    if encoded is None:
        return None
    if encoded == "":
        return ()
    points = []
    for point in encoded.split(_PAIR_SEPARATOR):
        x_str, y_str = point.split(",")
        points.append((float(x_str), float(y_str)))
    return tuple(points)


class ObservationRepository:
    """SQLite-backed repository boundary for Observation evidence.

    Observations are append-only evidence records (never edited in
    place), so unlike TrackGroupRepository this deliberately has no
    `save`/upsert -- only `add`.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def add(self, observation: Observation) -> None:
        roi = observation.roi
        with self._conn:
            self._conn.execute(
                "INSERT INTO observations "
                "(id, text, start_time, end_time, language, confidence, "
                "roi_x, roi_y, roi_width, roi_height, geometry, frame_reference, "
                "provenance_kind, provenance_source, provenance_detail) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    observation.id,
                    observation.text,
                    observation.start_time,
                    observation.end_time,
                    observation.language,
                    observation.confidence,
                    roi.x if roi is not None else None,
                    roi.y if roi is not None else None,
                    roi.width if roi is not None else None,
                    roi.height if roi is not None else None,
                    _encode_geometry(observation.geometry),
                    observation.frame_reference,
                    observation.provenance.kind.value,
                    observation.provenance.source,
                    _encode_detail(observation.provenance.detail),
                ),
            )

    def get(self, observation_id: str) -> Observation | None:
        row = self._conn.execute(
            "SELECT id, text, start_time, end_time, language, confidence, "
            "roi_x, roi_y, roi_width, roi_height, geometry, frame_reference, "
            "provenance_kind, provenance_source, provenance_detail "
            "FROM observations WHERE id = ?",
            (observation_id,),
        ).fetchone()
        if row is None:
            return None
        return self._build_observation(row)

    def list_all(self) -> list[Observation]:
        rows = self._conn.execute(
            "SELECT id, text, start_time, end_time, language, confidence, "
            "roi_x, roi_y, roi_width, roi_height, geometry, frame_reference, "
            "provenance_kind, provenance_source, provenance_detail "
            "FROM observations ORDER BY start_time"
        ).fetchall()
        return [self._build_observation(row) for row in rows]

    def _build_observation(self, row: tuple) -> Observation:
        (
            observation_id,
            text,
            start_time,
            end_time,
            language,
            confidence,
            roi_x,
            roi_y,
            roi_width,
            roi_height,
            geometry,
            frame_reference,
            provenance_kind,
            provenance_source,
            provenance_detail,
        ) = row
        roi = (
            ROI(x=roi_x, y=roi_y, width=roi_width, height=roi_height)
            if roi_x is not None
            else None
        )
        return Observation(
            id=observation_id,
            text=text,
            start_time=start_time,
            end_time=end_time,
            provenance=Provenance(
                kind=ProvenanceKind(provenance_kind),
                source=provenance_source,
                detail=_decode_detail(provenance_detail),
            ),
            language=language,
            confidence=confidence,
            roi=roi,
            geometry=_decode_geometry(geometry),
            frame_reference=frame_reference,
        )
