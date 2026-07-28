"""Code chunks: the addressable unit of retrieval and evidence.

A chunk's identity is content-addressed over everything that could change
what it means — the commit, its location, its text, and the chunker version.
Two consequences follow: re-indexing an unchanged file reuses its chunks (and
their embeddings), and a chunk can never be silently reinterpreted after a
chunker change, because a new chunker version yields new ids.
"""

from __future__ import annotations

from dataclasses import dataclass

from issuepilot.knowledge.domain.values import ChunkKind
from issuepilot.shared_kernel.hashing import content_hash, sha256_hex


@dataclass(frozen=True, slots=True)
class CodeChunk:
    chunk_id: str
    commit_sha: str
    path: str
    start_line: int
    end_line: int
    text: str
    kind: ChunkKind
    content_hash: str
    symbol: str | None = None
    language: str | None = None

    def __post_init__(self) -> None:
        if self.start_line < 1 or self.end_line < self.start_line:
            raise ValueError(
                f"invalid chunk line range {self.start_line}-{self.end_line} in {self.path}"
            )
        if not self.path:
            raise ValueError("a chunk requires a path")

    @property
    def line_count(self) -> int:
        return self.end_line - self.start_line + 1


def make_chunk_id(
    *,
    commit_sha: str,
    path: str,
    start_line: int,
    end_line: int,
    text_hash: str,
    chunker_version: str,
) -> str:
    parts = (commit_sha, path, str(start_line), str(end_line), text_hash, chunker_version)
    return sha256_hex("\0".join(parts).encode("utf-8"))


def build_chunk(
    *,
    commit_sha: str,
    path: str,
    start_line: int,
    end_line: int,
    text: str,
    kind: ChunkKind,
    chunker_version: str,
    symbol: str | None = None,
    language: str | None = None,
) -> CodeChunk:
    text_hash = content_hash(text)
    return CodeChunk(
        chunk_id=make_chunk_id(
            commit_sha=commit_sha,
            path=path,
            start_line=start_line,
            end_line=end_line,
            text_hash=text_hash,
            chunker_version=chunker_version,
        ),
        commit_sha=commit_sha,
        path=path,
        start_line=start_line,
        end_line=end_line,
        text=text,
        kind=kind,
        content_hash=text_hash,
        symbol=symbol,
        language=language,
    )
