"""Lexical search over SQLite FTS5.

Query text reaches this adapter from two untrusted-ish places: the user's
issue statement and the model's tool arguments. FTS5 has its own query
syntax, so raw text can be a syntax error (``foo(bar``) or, worse, silently
mean something the caller never intended (``NOT``, ``*``, column filters).
Every term is therefore quoted as a literal phrase, and the query is built
from extracted terms rather than passed through.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Sequence
from typing import Final

from issuepilot.knowledge.domain.chunk import CodeChunk

LEXICAL_VERSION: Final = "1"

# Terms are alphanumeric runs, keeping '_' so snake_case identifiers survive.
_TERM_RE: Final = re.compile(r"[A-Za-z0-9_]+")
_MAX_TERMS: Final = 32


class Fts5LexicalIndex:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def index(self, chunks: Sequence[CodeChunk]) -> None:
        self._connection.executemany(
            "INSERT INTO knw_chunks_fts (chunk_id, commit_sha, text, symbol, path)"
            " VALUES (?, ?, ?, ?, ?)",
            [(c.chunk_id, c.commit_sha, c.text, c.symbol or "", c.path) for c in chunks],
        )

    def search(self, commit_sha: str, query: str, *, limit: int) -> Sequence[str]:
        match_expression = build_match_query(query)
        if match_expression is None:
            return []
        rows = self._connection.execute(
            "SELECT chunk_id FROM knw_chunks_fts"
            " WHERE knw_chunks_fts MATCH ? AND commit_sha = ?"
            " ORDER BY bm25(knw_chunks_fts, 1.0, 4.0, 2.0) LIMIT ?",
            (match_expression, commit_sha, limit),
        ).fetchall()
        return [row["chunk_id"] for row in rows]

    def clear(self, commit_sha: str) -> None:
        self._connection.execute("DELETE FROM knw_chunks_fts WHERE commit_sha = ?", (commit_sha,))


def build_match_query(query: str) -> str | None:
    """Turn free text into a safe FTS5 MATCH expression, or None if empty.

    Terms are OR-ed so a multi-word query still retrieves partial matches;
    ranking, not filtering, decides what surfaces first.
    """
    terms = _TERM_RE.findall(query)[:_MAX_TERMS]
    if not terms:
        return None
    # Double quotes are the FTS5 phrase delimiter; a literal one is escaped by
    # doubling. Terms cannot contain quotes given the pattern, but quoting
    # unconditionally keeps this correct if the pattern ever widens.
    quoted = [f'"{term.replace(chr(34), chr(34) * 2)}"' for term in terms]
    return " OR ".join(quoted)
