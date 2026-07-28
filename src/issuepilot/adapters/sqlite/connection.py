"""SQLite connection management.

One database file holds every context's tables (ownership by prefix: ``rep_``,
``knw_``, ``inv_``, ``evl_``, ``gov_``, ``fbk_``, plus ``outbox_events``).
WAL mode is enabled from day one so a future daemon can serve reads while a
writer works.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def connect(db_path: Path | str) -> sqlite3.Connection:
    """Open a connection with the project's required pragmas applied."""
    if isinstance(db_path, Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
    # isolation_level=None puts sqlite3 in autocommit; transactions are always
    # explicit via the transaction() context manager below.
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Explicit write transaction: ``BEGIN IMMEDIATE`` … ``COMMIT``/``ROLLBACK``."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def has_fts5(conn: sqlite3.Connection) -> bool:
    """Whether this SQLite build ships the FTS5 extension."""
    row = conn.execute(
        "SELECT count(*) FROM pragma_compile_options WHERE compile_options = 'ENABLE_FTS5'"
    ).fetchone()
    return bool(row[0])
