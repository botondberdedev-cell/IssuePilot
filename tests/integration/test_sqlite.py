from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import pytest

from issuepilot.adapters.sqlite.connection import connect, has_fts5, transaction
from issuepilot.adapters.sqlite.migrator import migrate, schema_version

pytestmark = pytest.mark.integration


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "issuepilot.db"


@pytest.fixture
def conn(db_path: Path) -> Iterator[sqlite3.Connection]:
    connection = connect(db_path)
    try:
        yield connection
    finally:
        connection.close()


def test_file_database_uses_wal_and_fts5(conn: sqlite3.Connection) -> None:
    row = conn.execute("PRAGMA journal_mode").fetchone()
    assert row[0] == "wal"
    assert has_fts5(conn), "SQLite build must ship FTS5"


def test_migrations_survive_reconnect(db_path: Path) -> None:
    with closing(connect(db_path)) as first:
        migrate(first)
        version = schema_version(first)

    with closing(connect(db_path)) as reopened:
        assert schema_version(reopened) == version
        assert migrate(reopened) == []


def test_transaction_rolls_back_on_error(conn: sqlite3.Connection) -> None:
    migrate(conn)

    def insert_then_fail() -> None:
        with transaction(conn):
            conn.execute(
                "INSERT INTO outbox_events"
                " (event_id, event_type, aggregate_id, occurred_at, payload)"
                " VALUES ('e1', 'T', 'a1', '2026-07-28T00:00:00+00:00', '{}')"
            )
            raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        insert_then_fail()
    count = conn.execute("SELECT count(*) FROM outbox_events").fetchone()[0]
    assert count == 0


def test_transaction_commits_on_success(conn: sqlite3.Connection, db_path: Path) -> None:
    migrate(conn)
    with transaction(conn):
        conn.execute(
            "INSERT INTO outbox_events (event_id, event_type, aggregate_id, occurred_at, payload)"
            " VALUES ('e1', 'T', 'a1', '2026-07-28T00:00:00+00:00', '{}')"
        )
    # A separate connection proves the write is committed, not just cached.
    with closing(sqlite3.connect(db_path)) as other:
        count = other.execute("SELECT count(*) FROM outbox_events").fetchone()[0]
    assert count == 1
