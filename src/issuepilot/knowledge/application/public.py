"""The knowledge context's public facade."""

from __future__ import annotations

from issuepilot.knowledge.application.dto import IndexStatsDTO, SearchHitDTO
from issuepilot.knowledge.application.ports import ChunkStorePort
from issuepilot.knowledge.application.use_cases.build_index import (
    BuildIndex,
    BuildIndexCommand,
)
from issuepilot.knowledge.application.use_cases.search import Search, SearchCommand
from issuepilot.shared_kernel.cancellation import NEVER_CANCELLED, CancellationToken


class KnowledgeFacade:
    def __init__(self, build: BuildIndex, search: Search, chunks: ChunkStorePort) -> None:
        self._build = build
        self._search = search
        self._chunks = chunks

    def build_index(
        self, commit_sha: str, *, cancellation: CancellationToken = NEVER_CANCELLED
    ) -> IndexStatsDTO:
        return self._build.execute(BuildIndexCommand(commit_sha), cancellation=cancellation)

    def search(self, commit_sha: str, query: str, *, limit: int = 12) -> list[SearchHitDTO]:
        return self._search.execute(SearchCommand(commit_sha=commit_sha, query=query, limit=limit))

    def stats(self, commit_sha: str) -> IndexStatsDTO:
        return IndexStatsDTO(
            commit_sha=commit_sha,
            chunk_count=self._chunks.count_for_commit(commit_sha),
            indexed_files=0,
            has_semantic=self._search.has_semantic,
        )

    def is_indexed(self, commit_sha: str) -> bool:
        return self._chunks.count_for_commit(commit_sha) > 0
