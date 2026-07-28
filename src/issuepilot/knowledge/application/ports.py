"""Ports required by knowledge use cases."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from issuepilot.knowledge.domain.chunk import CodeChunk


@dataclass(frozen=True, slots=True)
class SourceFile:
    """One eligible file to be indexed, with its content already read."""

    path: str
    text: str
    language: str | None


class SourcePort(Protocol):
    """Eligible file content for a snapshot, served by the repository context."""

    def eligible_files(self, commit_sha: str) -> Sequence[SourceFile]: ...


class ChunkStorePort(Protocol):
    def put_many(self, chunks: Sequence[CodeChunk]) -> None: ...

    def get(self, chunk_id: str) -> CodeChunk | None: ...

    def get_many(self, chunk_ids: Sequence[str]) -> list[CodeChunk]:
        """Fetch several chunks at once, preserving the requested order and
        silently omitting ids the store does not have."""
        ...

    def count_for_commit(self, commit_sha: str) -> int: ...

    def delete_for_commit(self, commit_sha: str) -> None: ...


class LexicalIndexPort(Protocol):
    """Full-text search over chunk text, returning chunk ids best-first."""

    def index(self, chunks: Sequence[CodeChunk]) -> None: ...

    def search(self, commit_sha: str, query: str, *, limit: int) -> Sequence[str]: ...

    def clear(self, commit_sha: str) -> None: ...


class EmbeddingGeneratorPort(Protocol):
    """Batch text embedding. Returned vectors are unit-length."""

    @property
    def dimension(self) -> int: ...

    @property
    def model_name(self) -> str: ...

    def embed(self, texts: Sequence[str]) -> list[tuple[float, ...]]: ...


class VectorIndexPort(Protocol):
    """Nearest-neighbour search over normalized vectors (dot product)."""

    def add(self, commit_sha: str, entries: Sequence[tuple[str, tuple[float, ...]]]) -> None: ...

    def search(self, commit_sha: str, query: tuple[float, ...], *, limit: int) -> Sequence[str]: ...

    def clear(self, commit_sha: str) -> None: ...
