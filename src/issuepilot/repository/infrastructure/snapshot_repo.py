"""SQLite-backed snapshot records."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence

from issuepilot.repository.application.ports import SnapshotRecord
from issuepilot.repository.domain.values import CommitSha, RepositoryRef
from issuepilot.shared_kernel.ids import SnapshotId


class SqliteSnapshotStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def put(self, record: SnapshotRecord) -> None:
        self._connection.execute(
            "INSERT OR REPLACE INTO rep_snapshots"
            " (snapshot_id, locator_fingerprint, requested_ref, commit_sha, root_path)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                record.snapshot_id,
                record.locator_fingerprint,
                record.requested_ref.value,
                record.commit_sha.value,
                record.root_path,
            ),
        )

    def get(self, snapshot_id: SnapshotId) -> SnapshotRecord | None:
        row = self._connection.execute(
            "SELECT * FROM rep_snapshots WHERE snapshot_id = ?", (snapshot_id,)
        ).fetchone()
        return _to_record(row) if row is not None else None

    def find_by_commit(self, locator_fingerprint: str, sha: CommitSha) -> SnapshotRecord | None:
        row = self._connection.execute(
            "SELECT * FROM rep_snapshots WHERE locator_fingerprint = ? AND commit_sha = ?",
            (locator_fingerprint, sha.value),
        ).fetchone()
        return _to_record(row) if row is not None else None

    def list_recent(self, limit: int = 20) -> Sequence[SnapshotRecord]:
        # Snapshot ids are ULIDs, so descending id order is newest first.
        rows = self._connection.execute(
            "SELECT * FROM rep_snapshots ORDER BY snapshot_id DESC LIMIT ?", (limit,)
        ).fetchall()
        return tuple(_to_record(row) for row in rows)


def _to_record(row: sqlite3.Row) -> SnapshotRecord:
    return SnapshotRecord(
        snapshot_id=SnapshotId(row["snapshot_id"]),
        locator_fingerprint=row["locator_fingerprint"],
        requested_ref=RepositoryRef(row["requested_ref"]),
        commit_sha=CommitSha(row["commit_sha"]),
        root_path=row["root_path"],
    )
