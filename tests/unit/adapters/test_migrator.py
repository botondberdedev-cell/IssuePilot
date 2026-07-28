from __future__ import annotations

import sqlite3

import pytest

from issuepilot.adapters.sqlite.connection import connect
from issuepilot.adapters.sqlite.migrator import (
    discover_migrations,
    migrate,
    schema_version,
)
from issuepilot.shared_kernel.errors import InternalError


@pytest.fixture
def conn() -> sqlite3.Connection:
    return connect(":memory:")


def test_discovered_migrations_are_contiguous_from_one() -> None:
    migrations = discover_migrations()
    assert migrations, "at least one migration must exist"
    assert [m.number for m in migrations] == list(range(1, len(migrations) + 1))


def test_migrate_fresh_database_reaches_head(conn: sqlite3.Connection) -> None:
    applied = migrate(conn)
    assert applied == [m.name for m in discover_migrations()]
    assert schema_version(conn) == len(discover_migrations())


def test_migrate_is_idempotent(conn: sqlite3.Connection) -> None:
    migrate(conn)
    assert migrate(conn) == []


def test_newer_schema_than_build_is_rejected(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA user_version = 9999")
    with pytest.raises(InternalError, match="newer than this build"):
        migrate(conn)


def test_outbox_table_exists_after_migration(conn: sqlite3.Connection) -> None:
    migrate(conn)
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='outbox_events'"
    ).fetchone()
    assert row is not None
