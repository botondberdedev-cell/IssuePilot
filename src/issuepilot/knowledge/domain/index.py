"""The knowledge index aggregate.

An index is only valid for the exact combination of inputs that produced it.
That combination — the index key — includes the embedding model digest,
because vectors from a different model are not comparable, and the chunker
version, because chunk ids would differ. Changing any component yields a
different key, which is how a stale index is detected rather than silently
reused.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum, unique

from issuepilot.shared_kernel.hashing import canonical_json_hash
from issuepilot.shared_kernel.ids import IndexId


@unique
class IndexState(Enum):
    BUILDING = "building"
    READY = "ready"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class IndexKey:
    """Everything an index's validity depends on."""

    commit_sha: str
    chunker_version: str
    lexical_version: str
    embedding_model: str | None = None
    embedding_dimension: int | None = None

    def __post_init__(self) -> None:
        if not self.commit_sha:
            raise ValueError("an index key requires a commit sha")
        has_model = self.embedding_model is not None
        has_dimension = self.embedding_dimension is not None
        if has_model != has_dimension:
            raise ValueError(
                "embedding model and dimension must be set together; "
                "a semantic index needs both to be comparable"
            )

    @property
    def has_semantic(self) -> bool:
        return self.embedding_model is not None

    def fingerprint(self) -> str:
        return canonical_json_hash(
            {
                "commit_sha": self.commit_sha,
                "chunker_version": self.chunker_version,
                "lexical_version": self.lexical_version,
                "embedding_model": self.embedding_model,
                "embedding_dimension": self.embedding_dimension,
            }
        )


class IndexTransitionError(Exception):
    """An illegal state transition was attempted on an index."""


@dataclass(frozen=True, slots=True)
class KnowledgeIndex:
    index_id: IndexId
    key: IndexKey
    state: IndexState = IndexState.BUILDING
    chunk_count: int = 0
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if self.chunk_count < 0:
            raise ValueError("chunk count cannot be negative")
        if self.state is IndexState.FAILED and not self.failure_reason:
            raise ValueError("a FAILED index requires a reason")

    def complete(self, chunk_count: int) -> KnowledgeIndex:
        if self.state is not IndexState.BUILDING:
            raise IndexTransitionError(f"cannot complete an index that is {self.state.value}")
        return replace(self, state=IndexState.READY, chunk_count=chunk_count)

    def fail(self, reason: str) -> KnowledgeIndex:
        if self.state is not IndexState.BUILDING:
            raise IndexTransitionError(f"cannot fail an index that is {self.state.value}")
        return replace(self, state=IndexState.FAILED, failure_reason=reason)

    def accepts(self, key: IndexKey) -> bool:
        """Whether this index can serve a query built for ``key``."""
        return self.state is IndexState.READY and self.key == key
