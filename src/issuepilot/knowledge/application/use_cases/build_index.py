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
    LexicalIndexPort,
    SourcePort,
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
    ) -> None:
        self._source = source
        self._chunks = chunks
        self._lexical = lexical
        self._ids = ids
        self._clock = clock
        self._bus = bus

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
                    self._flush(pending)
                    pending = []
            self._flush(pending)
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
            has_semantic=False,
        )

    def _flush(self, pending: list[CodeChunk]) -> None:
        if not pending:
            return
        self._chunks.put_many(pending)
        self._lexical.index(pending)
