"""Wires the knowledge context, including the repository→source translator.

The translator is the sanctioned bridge between two independent contexts:
knowledge declares a ``SourcePort`` describing what it needs, and this module
satisfies it from the repository facade. Neither context imports the other.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from pathlib import Path

from issuepilot.adapters.ollama.client import OllamaClient
from issuepilot.knowledge.application.dto import IndexStatsDTO, SearchHitDTO
from issuepilot.knowledge.application.ports import SourceFile
from issuepilot.knowledge.application.public import KnowledgeFacade
from issuepilot.knowledge.application.use_cases.build_index import BuildIndex
from issuepilot.knowledge.application.use_cases.search import Search
from issuepilot.knowledge.infrastructure.chunk_repo import SqliteChunkStore
from issuepilot.knowledge.infrastructure.fts5_index import Fts5LexicalIndex
from issuepilot.knowledge.infrastructure.numpy_vectors import NumpyVectorIndex
from issuepilot.knowledge.infrastructure.ollama_embedder import OllamaEmbedder
from issuepilot.repository.application.public import RepositoryFacade
from issuepilot.repository.domain.manifest import detect_language
from issuepilot.repository.domain.values import RelativeRepoPath
from issuepilot.shared_kernel.clock import Clock
from issuepilot.shared_kernel.events import EventBus
from issuepilot.shared_kernel.ids import IdGenerator

_MAX_SOURCE_LINES = 200_000


class RepositorySourceTranslator:
    """Serves knowledge's SourcePort from the repository context's facade.

    A snapshot's root is registered after acquisition; without it there is
    nothing to read, and reporting no files is the honest answer.
    """

    def __init__(self, repository: RepositoryFacade) -> None:
        self._repository = repository
        self._roots: dict[str, str] = {}

    def register_snapshot(self, commit_sha: str, root_path: str) -> None:
        self._roots[commit_sha] = root_path

    def eligible_files(self, commit_sha: str) -> Sequence[SourceFile]:
        root = self._roots.get(commit_sha)
        if root is None:
            return ()
        files: list[SourceFile] = []
        for path in self._repository.analyzable_paths(commit_sha):
            line_count = self._repository.line_count(root, path)
            if line_count == 0:
                continue
            slice_ = self._repository.read_slice(
                root, commit_sha, path, 1, min(line_count, _MAX_SOURCE_LINES)
            )
            files.append(
                SourceFile(
                    path=path,
                    text=slice_.text,
                    language=detect_language(RelativeRepoPath(path)),
                )
            )
        return tuple(files)


def build_knowledge_facade(
    *,
    connection: sqlite3.Connection,
    workspace_dir: Path,
    source: RepositorySourceTranslator,
    ids: IdGenerator,
    clock: Clock,
    bus: EventBus,
    ollama_url: str,
    embedding_model: str,
    semantic_enabled: bool,
) -> KnowledgeFacade:
    chunks = SqliteChunkStore(connection)
    lexical = Fts5LexicalIndex(connection)

    vectors = NumpyVectorIndex(workspace_dir / "indexes") if semantic_enabled else None
    embedder = (
        OllamaEmbedder(OllamaClient(ollama_url), embedding_model) if semantic_enabled else None
    )

    build = BuildIndex(
        source=source,
        chunks=chunks,
        lexical=lexical,
        ids=ids,
        clock=clock,
        bus=bus,
        vectors=vectors,
        embedder=embedder,
    )
    search = Search(chunks=chunks, lexical=lexical, vectors=vectors, embedder=embedder)
    return KnowledgeFacade(build, search, chunks)


class KnowledgeServiceAdapter:
    """Presents the knowledge facade in the primitives the CLI speaks.

    Registering the snapshot root here is what lets the CLI ask for indexing
    by commit alone, with neither side handling filesystem paths.
    """

    def __init__(self, facade: KnowledgeFacade, source: RepositorySourceTranslator) -> None:
        self._facade = facade
        self._source = source

    def build_index(
        self, commit_sha: str, root_path: str, *, rebuild: bool = False
    ) -> IndexStatsDTO:
        self._source.register_snapshot(commit_sha, root_path)
        if not rebuild and self._facade.is_indexed(commit_sha):
            return self._facade.stats(commit_sha)
        return self._facade.build_index(commit_sha)

    def search(self, commit_sha: str, query: str, *, limit: int = 12) -> list[SearchHitDTO]:
        return self._facade.search(commit_sha, query, limit=limit)

    def is_indexed(self, commit_sha: str) -> bool:
        return self._facade.is_indexed(commit_sha)
