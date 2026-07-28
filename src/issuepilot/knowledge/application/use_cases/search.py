"""Hybrid retrieval: lexical and (when available) semantic, fused by rank.

The lexical path works with no model present, which is deliberate — the tool
stays useful when Ollama is not running, and it means retrieval quality can
be evaluated independently of the embedding model.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from issuepilot.knowledge.application.dto import SearchHitDTO
from issuepilot.knowledge.application.ports import (
    ChunkStorePort,
    EmbeddingGeneratorPort,
    LexicalIndexPort,
    VectorIndexPort,
)
from issuepilot.knowledge.domain.fusion import diversify, reciprocal_rank_fusion

_SNIPPET_CHARS = 600


@dataclass(frozen=True, slots=True)
class SearchCommand:
    commit_sha: str
    query: str
    limit: int = 12
    lexical_candidates: int = 40
    semantic_candidates: int = 40
    per_file: int = 2
    """Cap on chunks from one file, so a verbose document cannot crowd out
    the code it describes."""


class Search:
    def __init__(
        self,
        *,
        chunks: ChunkStorePort,
        lexical: LexicalIndexPort,
        vectors: VectorIndexPort | None = None,
        embedder: EmbeddingGeneratorPort | None = None,
    ) -> None:
        self._chunks = chunks
        self._lexical = lexical
        self._vectors = vectors
        self._embedder = embedder

    @property
    def has_semantic(self) -> bool:
        return self._vectors is not None and self._embedder is not None

    def execute(self, command: SearchCommand) -> list[SearchHitDTO]:
        if not command.query.strip():
            return []

        ranked: dict[str, Sequence[str]] = {
            "lexical": self._lexical.search(
                command.commit_sha, command.query, limit=command.lexical_candidates
            )
        }
        semantic = self._semantic_search(command)
        if semantic is not None:
            ranked["semantic"] = semantic

        fused = reciprocal_rank_fusion(ranked)
        if not fused:
            return []

        # Diversify before truncating: the cap must apply to what the caller
        # sees, not to an already-truncated list.
        loaded = {c.chunk_id: c for c in self._chunks.get_many([r.key for r in fused])}
        fused = diversify(
            [r for r in fused if r.key in loaded],
            lambda r: loaded[r.key].path,
            per_group=command.per_file,
            limit=command.limit,
        )
        by_id = loaded
        hits: list[SearchHitDTO] = []
        for result in fused:
            chunk = by_id.get(result.key)
            if chunk is None:
                # The index referenced a chunk the store no longer has; skipping
                # is correct — a hit we cannot describe cannot become evidence.
                continue
            hits.append(
                SearchHitDTO(
                    chunk_id=chunk.chunk_id,
                    path=chunk.path,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    commit_sha=chunk.commit_sha,
                    snippet=chunk.text[:_SNIPPET_CHARS],
                    score=result.score,
                    sources=result.sources,
                    symbol=chunk.symbol,
                )
            )
        return hits

    def _semantic_search(self, command: SearchCommand) -> Sequence[str] | None:
        if self._vectors is None or self._embedder is None:
            return None
        (vector,) = self._embedder.embed([command.query])
        return self._vectors.search(command.commit_sha, vector, limit=command.semantic_candidates)
