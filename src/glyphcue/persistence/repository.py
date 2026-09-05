from __future__ import annotations

import sqlite3

from glyphcue.domain.cue import Cue
from glyphcue.domain.language_layer import LanguageLayer
from glyphcue.domain.review_state import ReviewState

_OBSERVATION_ID_SEPARATOR = "\x1f"


class CueRepository:
    """SQLite-backed repository boundary for Cue aggregates.

    Callers interact only with domain objects (Cue / LanguageLayer);
    SQLite row shapes never leak past this module.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def add(self, cue: Cue, source_id: str = "") -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO cues (id, start_time, end_time, review_state, source_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (cue.id, cue.start_time, cue.end_time, cue.review_state.value, source_id),
            )
            for position, layer in enumerate(cue.language_layers):
                self._conn.execute(
                    "INSERT INTO language_layers "
                    "(cue_id, position, language, text, observation_ids) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        cue.id,
                        position,
                        layer.language,
                        layer.text,
                        _OBSERVATION_ID_SEPARATOR.join(layer.observation_ids),
                    ),
                )

    def update_cue_state(self, cue_id: str, review_state: ReviewState) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE cues SET review_state = ? WHERE id = ?",
                (review_state.value, cue_id),
            )

    def get(self, cue_id: str) -> Cue | None:
        row = self._conn.execute(
            "SELECT id, start_time, end_time, review_state FROM cues WHERE id = ?",
            (cue_id,),
        ).fetchone()
        if row is None:
            return None
        return self._build_cue(row)

    def list_all(self) -> list[Cue]:
        rows = self._conn.execute(
            "SELECT id, start_time, end_time, review_state FROM cues ORDER BY start_time, end_time, id"
        ).fetchall()
        return [self._build_cue(row) for row in rows]

    def list_for_source(self, source_id: str) -> list[Cue]:
        if not source_id:
            return []
        rows = self._conn.execute(
            "SELECT id, start_time, end_time, review_state FROM cues "
            "WHERE source_id = ? ORDER BY start_time, end_time, id",
            (source_id,),
        ).fetchall()
        return [self._build_cue(row) for row in rows]

    def save_cues_for_source(self, source_id: str, cues: list[Cue]) -> None:
        """Atomically replaces all cues and language layers for `source_id`."""
        with self._conn:
            self._conn.execute(
                "DELETE FROM language_layers WHERE cue_id IN (SELECT id FROM cues WHERE source_id = ?)",
                (source_id,),
            )
            self._conn.execute(
                "DELETE FROM cues WHERE source_id = ?",
                (source_id,),
            )
            for cue in cues:
                self._conn.execute(
                    "INSERT INTO cues (id, start_time, end_time, review_state, source_id) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (cue.id, cue.start_time, cue.end_time, cue.review_state.value, source_id),
                )
                for position, layer in enumerate(cue.language_layers):
                    self._conn.execute(
                        "INSERT INTO language_layers "
                        "(cue_id, position, language, text, observation_ids) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (
                            cue.id,
                            position,
                            layer.language,
                            layer.text,
                            _OBSERVATION_ID_SEPARATOR.join(layer.observation_ids),
                        ),
                    )

    def delete_for_source(self, source_id: str) -> None:
        """Deletes all cues and language layers for `source_id`."""
        with self._conn:
            self._conn.execute(
                "DELETE FROM language_layers WHERE cue_id IN (SELECT id FROM cues WHERE source_id = ?)",
                (source_id,),
            )
            self._conn.execute(
                "DELETE FROM cues WHERE source_id = ?",
                (source_id,),
            )


    def _build_cue(self, row: tuple) -> Cue:
        cue_id, start_time, end_time, review_state = row
        layer_rows = self._conn.execute(
            "SELECT language, text, observation_ids FROM language_layers "
            "WHERE cue_id = ? ORDER BY position",
            (cue_id,),
        ).fetchall()
        layers = tuple(
            LanguageLayer(
                language=language,
                text=text,
                observation_ids=tuple(
                    observation_ids.split(_OBSERVATION_ID_SEPARATOR)
                    if observation_ids
                    else ()
                ),
            )
            for language, text, observation_ids in layer_rows
        )
        return Cue(
            id=cue_id,
            start_time=start_time,
            end_time=end_time,
            language_layers=layers,
            review_state=ReviewState(review_state),
        )
