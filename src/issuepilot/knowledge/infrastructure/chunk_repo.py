"""SQLite-backed chunk storage."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence

from issuepilot.knowledge.domain.chunk import CodeChunk
from issuepilot.knowledge.domain.values import ChunkKind


class SqliteChunkStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def put_many(self, chunks: Sequence[CodeChunk]) -> None:
        self._connection.executemany(
            "INSERT OR REPLACE INTO knw_chunks"
            " (chunk_id, commit_sha, path, start_line, end_line, text, kind,"
            "  content_hash, symbol, language)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    c.chunk_id,
                    c.commit_sha,
                    c.path,
                    c.start_line,
                    c.end_line,
                    c.text,
                    c.kind.value,
                    c.content_hash,
                    c.symbol,
                    c.language,
                )
                for c in chunks
            ],
        )

    def get(self, chunk_id: str) -> CodeChunk | None:
        row = self._connection.execute(
            "SELECT * FROM knw_chunks WHERE chunk_id = ?", (chunk_id,)
        ).fetchone()
        return _to_chunk(row) if row is not None else None

    def get_many(self, chunk_ids: Sequence[str]) -> list[CodeChunk]:
        """Fetch in one round trip, preserving the caller's ordering."""
        if not chunk_ids:
            return []
        placeholders = ",".join("?" for _ in chunk_ids)
        rows = self._connection.execute(
            f"SELECT * FROM knw_chunks WHERE chunk_id IN ({placeholders})",  # noqa: S608
            tuple(chunk_ids),
        ).fetchall()
        by_id = {row["chunk_id"]: _to_chunk(row) for row in rows}
        return [by_id[cid] for cid in chunk_ids if cid in by_id]

    def count_for_commit(self, commit_sha: str) -> int:
        row = self._connection.execute(
            "SELECT count(*) AS n FROM knw_chunks WHERE commit_sha = ?", (commit_sha,)
        ).fetchone()
        return int(row["n"])

    def delete_for_commit(self, commit_sha: str) -> None:
        self._connection.execute("DELETE FROM knw_chunks WHERE commit_sha = ?", (commit_sha,))


def _to_chunk(row: sqlite3.Row) -> CodeChunk:
    return CodeChunk(
        chunk_id=row["chunk_id"],
        commit_sha=row["commit_sha"],
        path=row["path"],
        start_line=row["start_line"],
        end_line=row["end_line"],
        text=row["text"],
        kind=ChunkKind(row["kind"]),
        content_hash=row["content_hash"],
        symbol=row["symbol"],
        language=row["language"],
    )
