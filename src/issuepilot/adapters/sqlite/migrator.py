"""Forward-only migration runner keyed on ``PRAGMA user_version``.

Migrations are numbered SQL files packaged in
``issuepilot.adapters.sqlite.migrations`` (``0001_outbox.sql``, …). Each file
is applied inside a single transaction together with the ``user_version``
bump, so a crash can never leave a migration half-applied but marked done.

Migration files must not contain their own ``BEGIN``/``COMMIT`` statements.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from importlib import resources

from issuepilot.shared_kernel.errors import InternalError

_MIGRATION_NAME = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")
_MIGRATIONS_PACKAGE = "issuepilot.adapters.sqlite.migrations"


@dataclass(frozen=True, slots=True)
class Migration:
    number: int
    name: str
    sql: str


def discover_migrations() -> list[Migration]:
    """Load packaged migrations, validated to be contiguous from 1."""
    found: list[Migration] = []
    for entry in resources.files(_MIGRATIONS_PACKAGE).iterdir():
        if not entry.name.endswith(".sql"):
            continue
        match = _MIGRATION_NAME.match(entry.name)
        if match is None:
            raise InternalError(f"malformed migration filename: {entry.name}")
        found.append(Migration(int(match.group(1)), entry.name, entry.read_text(encoding="utf-8")))
    found.sort(key=lambda m: m.number)
    expected = list(range(1, len(found) + 1))
    if [m.number for m in found] != expected:
        raise InternalError(
            f"migrations must be contiguous from 0001; found {[m.name for m in found]}"
        )
    return found


def schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("PRAGMA user_version").fetchone()
    return int(row[0])


def migrate(conn: sqlite3.Connection) -> list[str]:
    """Apply pending migrations; returns the names applied (possibly empty)."""
    migrations = discover_migrations()
    current = schema_version(conn)
    if current > len(migrations):
        raise InternalError(
            f"database schema version {current} is newer than this build "
            f"(latest known migration is {len(migrations)})",
            remediation="upgrade issuepilot",
        )
    applied: list[str] = []
    for migration in migrations:
        if migration.number <= current:
            continue
        conn.executescript(
            f"BEGIN;\n{migration.sql}\nPRAGMA user_version = {migration.number};\nCOMMIT;"
        )
        applied.append(migration.name)
    return applied
