import sqlite3
import threading

from glyphcue.persistence.database import connect


def test_connect_returns_migrated_connection(tmp_path):
    db_path = tmp_path / "glyphcue.sqlite3"

    conn = connect(db_path)

    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    assert "cues" in tables
    assert db_path.exists()


def test_connect_enforces_foreign_keys(tmp_path):
    conn = connect(tmp_path / "glyphcue.sqlite3")

    (enabled,) = conn.execute("PRAGMA foreign_keys").fetchone()
    assert enabled == 1


def test_a_connection_cannot_be_used_from_a_different_thread_than_it_was_created_on(tmp_path):
    # Guards against reintroducing a blanket check_same_thread=False:
    # sharing one lockless connection between the UI thread and a
    # background job's worker thread is a real cross-thread hazard, not
    # just an sqlite3 formality. The fix is connection separation (each
    # thread opens its own connection to the same file -- see the next
    # test), not disabling this check.
    conn = connect(tmp_path / "glyphcue.sqlite3")
    errors = []

    def use_from_other_thread():
        try:
            conn.execute("SELECT 1")
        except Exception as exc:  # pragma: no cover - failure path under test
            errors.append(exc)

    thread = threading.Thread(target=use_from_other_thread)
    thread.start()
    thread.join(timeout=5)

    assert len(errors) == 1
    assert isinstance(errors[0], sqlite3.ProgrammingError)


def test_each_thread_can_use_its_own_connection_to_the_same_database_file(tmp_path):
    # The real pattern the Milestone 4 OCR evidence job uses: the UI
    # thread and the job's worker thread each call connect() themselves
    # and get their own connection object, rather than sharing one.
    db_path = tmp_path / "glyphcue.sqlite3"
    ui_conn = connect(db_path)
    errors = []

    def write_from_worker_thread():
        try:
            worker_conn = connect(db_path)
            worker_conn.execute(
                "INSERT INTO cues (id, start_time, end_time, review_state) "
                "VALUES ('c1', 0.0, 1.0, 'pending')"
            )
            worker_conn.commit()
            worker_conn.close()
        except Exception as exc:  # pragma: no cover - failure path under test
            errors.append(exc)

    thread = threading.Thread(target=write_from_worker_thread)
    thread.start()
    thread.join(timeout=5)

    assert errors == []
    row = ui_conn.execute("SELECT id FROM cues WHERE id = 'c1'").fetchone()
    assert row == ("c1",)
