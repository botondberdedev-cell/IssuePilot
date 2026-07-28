"""Build a knowledge index for one snapshot.

Indexing is idempotent per commit: a rebuild clears the commit's chunks and
lexical rows first, so re-running never accumulates duplicates. The work is
cancellable between files, and the file is the checkpoint unit — an
interrupted build leaves a partial index that the next run replaces wholesale
rather than trying to repair.
"""

from __future__ import annotations

from dataclasses import dataclass

from issuepilot.knowledge.application.dto import IndexStatsDTO
from issuepilot.knowledge.application.ports import (
    ChunkStorePort,
    EmbeddingGeneratorPort,
    LexicalIndexPort,
    SourcePort,
    VectorIndexPort,
)
from issuepilot.knowledge.domain.chunk import CodeChunk
from issuepilot.knowledge.domain.chunking import chunk_document
from issuepilot.knowledge.domain.events import KnowledgeIndexFailed, KnowledgeIndexReady
from issuepilot.shared_kernel.cancellation import NEVER_CANCELLED, CancellationToken
from issuepilot.shared_kernel.clock import Clock
from issuepilot.shared_kernel.events import EventBus
from issuepilot.shared_kernel.ids import EventId, IdGenerator

_BATCH_SIZE = 200


@dataclass(frozen=True, slots=True)
class BuildIndexCommand:
    commit_sha: str


class BuildIndex:
    def __init__(
        self,
        *,
        source: SourcePort,
        chunks: ChunkStorePort,
        lexical: LexicalIndexPort,
        ids: IdGenerator,
        clock: Clock,
        bus: EventBus,
        vectors: VectorIndexPort | None = None,
        embedder: EmbeddingGeneratorPort | None = None,
    ) -> None:
        self._source = source
        self._chunks = chunks
        self._lexical = lexical
        self._ids = ids
        self._clock = clock
        self._bus = bus
        self._vectors = vectors
        self._embedder = embedder

    @property
    def has_semantic(self) -> bool:
        return self._vectors is not None and self._embedder is not None

    def execute(
        self,
        command: BuildIndexCommand,
        *,
        cancellation: CancellationToken = NEVER_CANCELLED,
    ) -> IndexStatsDTO:
        commit_sha = command.commit_sha
        try:
            files = self._source.eligible_files(commit_sha)
            self._chunks.delete_for_commit(commit_sha)
            self._lexical.clear(commit_sha)
            if self._vectors is not None:
                self._vectors.clear(commit_sha)

            pending: list[CodeChunk] = []
            total = 0
            indexed_files = 0
            for file in files:
                cancellation.raise_if_cancelled()
                produced = chunk_document(
                    commit_sha=commit_sha,
                    path=file.path,
                    text=file.text,
                    language=file.language,
                )
                if not produced:
                    continue
                indexed_files += 1
                pending.extend(produced)
                total += len(produced)
                if len(pending) >= _BATCH_SIZE:
                    self._flush(pending, cancellation)
                    pending = []
            self._flush(pending, cancellation)
        except Exception as exc:
            self._bus.publish(
                KnowledgeIndexFailed(
                    event_id=EventId(self._ids.new_id()),
                    occurred_at=self._clock.now(),
                    aggregate_id=commit_sha,
                    snapshot_sha=commit_sha,
                    reason_category=type(exc).__name__,
                )
            )
            raise

        self._bus.publish(
            KnowledgeIndexReady(
                event_id=EventId(self._ids.new_id()),
                occurred_at=self._clock.now(),
                aggregate_id=commit_sha,
                index_id=commit_sha,
                snapshot_sha=commit_sha,
                chunk_count=total,
            )
        )
        return IndexStatsDTO(
            commit_sha=commit_sha,
            chunk_count=total,
            indexed_files=indexed_files,
            has_semantic=self.has_semantic,
        )

    def _flush(self, pending: list[CodeChunk], cancellation: CancellationToken) -> None:
        if not pending:
            return
        self._chunks.put_many(pending)
        self._lexical.index(pending)
        if self._vectors is None or self._embedder is None:
            return
        # Embedding is the slow part of a build, so check for cancellation
        # immediately before committing to a batch of model calls.
        cancellation.raise_if_cancelled()
        vectors = self._embedder.embed([chunk.text for chunk in pending])
        self._vectors.add(
            pending[0].commit_sha,
            [(chunk.chunk_id, vector) for chunk, vector in zip(pending, vectors, strict=True)],
        )
