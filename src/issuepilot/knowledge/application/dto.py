"""Immutable DTOs crossing the knowledge context's boundary."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SearchHitDTO:
    """One retrieval result, carrying enough to become evidence."""

    chunk_id: str
    path: str
    start_line: int
    end_line: int
    commit_sha: str
    snippet: str
    score: float
    sources: tuple[str, ...]
    """Which retrievers found it — kept so evaluation can attribute hits."""
    symbol: str | None = None


@dataclass(frozen=True, slots=True)
class IndexStatsDTO:
    commit_sha: str
    chunk_count: int
    indexed_files: int
    has_semantic: bool
