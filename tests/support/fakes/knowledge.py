from __future__ import annotations

from collections.abc import Sequence

from issuepilot.knowledge.application.ports import SourceFile
from issuepilot.knowledge.domain.chunk import CodeChunk


class InMemoryChunkStore:
    def __init__(self) -> None:
        self._chunks: dict[str, CodeChunk] = {}

    def put_many(self, chunks: Sequence[CodeChunk]) -> None:
        for chunk in chunks:
            self._chunks[chunk.chunk_id] = chunk

    def get(self, chunk_id: str) -> CodeChunk | None:
        return self._chunks.get(chunk_id)

    def get_many(self, chunk_ids: Sequence[str]) -> list[CodeChunk]:
        return [self._chunks[cid] for cid in chunk_ids if cid in self._chunks]

    def count_for_commit(self, commit_sha: str) -> int:
        return sum(1 for c in self._chunks.values() if c.commit_sha == commit_sha)

    def delete_for_commit(self, commit_sha: str) -> None:
        self._chunks = {k: v for k, v in self._chunks.items() if v.commit_sha != commit_sha}


class InMemoryLexicalIndex:
    """Substring matching over chunk text — enough to exercise the contract
    without reproducing BM25."""

    def __init__(self) -> None:
        self._chunks: list[CodeChunk] = []

    def index(self, chunks: Sequence[CodeChunk]) -> None:
        self._chunks.extend(chunks)

    def search(self, commit_sha: str, query: str, *, limit: int) -> Sequence[str]:
        terms = [t.lower() for t in query.split() if t.strip()]
        if not terms:
            return []
        scored: list[tuple[int, str]] = []
        for chunk in self._chunks:
            if chunk.commit_sha != commit_sha:
                continue
            haystack = f"{chunk.text} {chunk.symbol or ''} {chunk.path}".lower()
            hits = sum(haystack.count(term) for term in terms)
            if hits:
                scored.append((hits, chunk.chunk_id))
        scored.sort(key=lambda pair: (-pair[0], pair[1]))
        return [chunk_id for _, chunk_id in scored[:limit]]

    def clear(self, commit_sha: str) -> None:
        self._chunks = [c for c in self._chunks if c.commit_sha != commit_sha]


class InMemoryVectorIndex:
    def __init__(self) -> None:
        self._vectors: dict[str, list[tuple[str, tuple[float, ...]]]] = {}

    def add(self, commit_sha: str, entries: Sequence[tuple[str, tuple[float, ...]]]) -> None:
        self._vectors.setdefault(commit_sha, []).extend(entries)

    def search(self, commit_sha: str, query: tuple[float, ...], *, limit: int) -> Sequence[str]:
        entries = self._vectors.get(commit_sha, [])
        scored = [
            (sum(a * b for a, b in zip(query, vector, strict=False)), chunk_id)
            for chunk_id, vector in entries
        ]
        scored.sort(key=lambda pair: (-pair[0], pair[1]))
        return [chunk_id for _, chunk_id in scored[:limit]]

    def clear(self, commit_sha: str) -> None:
        self._vectors.pop(commit_sha, None)


class FakeSource:
    def __init__(self, files: Sequence[SourceFile] = ()) -> None:
        self._files = list(files)

    def add(self, path: str, text: str, language: str | None = None) -> None:
        self._files.append(SourceFile(path=path, text=text, language=language))

    def eligible_files(self, commit_sha: str) -> Sequence[SourceFile]:
        return tuple(self._files)
