"""Deterministic chunkers.

Chunking is a pure function of (path, text, language): same input, same
chunks, same ids. That is what makes an index reusable across runs and a
citation stable across re-indexing.

Structure-aware where it pays off — Python by top-level definition, Markdown
by heading — and line windows everywhere else. A structural chunk that grows
past ``MAX_CHUNK_LINES`` is split into windows rather than dominating a
retrieval budget on its own.
"""

from __future__ import annotations

import ast
import re
from typing import Final

from issuepilot.knowledge.domain.chunk import CodeChunk, build_chunk
from issuepilot.knowledge.domain.values import ChunkKind

CHUNKER_VERSION: Final = "1"

MAX_CHUNK_LINES: Final = 120
WINDOW_LINES: Final = 60
WINDOW_OVERLAP: Final = 10

_HEADING_RE: Final = re.compile(r"^(#{1,6})\s+(.*)$")
_DOC_LANGUAGES: Final = frozenset({"Markdown", "reStructuredText"})
_CONFIG_LANGUAGES: Final = frozenset({"YAML", "JSON", "TOML", "INI"})


def chunk_document(
    *, commit_sha: str, path: str, text: str, language: str | None
) -> list[CodeChunk]:
    """Split one file into chunks. Never raises on malformed content."""
    if not text.strip():
        return []
    lines = text.splitlines(keepends=True)

    if language == "Python":
        chunks = _chunk_python(commit_sha, path, text, lines, language)
        if chunks is not None:
            return chunks
        # Unparseable Python still deserves indexing; fall through to windows.
    if language in _DOC_LANGUAGES:
        return _chunk_markdown(commit_sha, path, lines, language)

    kind = ChunkKind.CONFIGURATION if language in _CONFIG_LANGUAGES else ChunkKind.CODE
    if language is None:
        kind = ChunkKind.OTHER
    return _windows(commit_sha, path, lines, 1, len(lines), kind, language, symbol=None)


def _chunk_python(
    commit_sha: str, path: str, text: str, lines: list[str], language: str
) -> list[CodeChunk] | None:
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return None

    chunks: list[CodeChunk] = []
    covered: set[int] = set()

    for node in tree.body:
        if not isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        start = _definition_start(node)
        end = node.end_lineno or start
        covered.update(range(start, end + 1))
        chunks.extend(
            _windows(
                commit_sha, path, lines, start, end, ChunkKind.CODE, language, symbol=node.name
            )
        )

    # Whatever sits outside definitions — imports, constants, module docstring —
    # is still meaningful context, so it becomes its own chunk.
    preamble = [n for n in range(1, len(lines) + 1) if n not in covered]
    for start, end in _contiguous_ranges(preamble):
        if not "".join(lines[start - 1 : end]).strip():
            continue
        chunks.extend(
            _windows(commit_sha, path, lines, start, end, ChunkKind.CODE, language, symbol=None)
        )

    chunks.sort(key=lambda c: (c.start_line, c.end_line))
    return chunks


def _definition_start(node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Include decorators: they carry meaning the definition depends on."""
    if node.decorator_list:
        return min(decorator.lineno for decorator in node.decorator_list)
    return node.lineno


def _chunk_markdown(
    commit_sha: str, path: str, lines: list[str], language: str | None
) -> list[CodeChunk]:
    boundaries: list[tuple[int, str | None]] = []
    for number, line in enumerate(lines, start=1):
        match = _HEADING_RE.match(line.rstrip("\n"))
        if match:
            boundaries.append((number, match.group(2).strip()))

    if not boundaries:
        return _windows(
            commit_sha, path, lines, 1, len(lines), ChunkKind.DOCUMENTATION, language, symbol=None
        )

    chunks: list[CodeChunk] = []
    # Content before the first heading is its own section.
    if boundaries[0][0] > 1:
        chunks.extend(
            _windows(
                commit_sha,
                path,
                lines,
                1,
                boundaries[0][0] - 1,
                ChunkKind.DOCUMENTATION,
                language,
                symbol=None,
            )
        )
    for index, (start, heading) in enumerate(boundaries):
        end = boundaries[index + 1][0] - 1 if index + 1 < len(boundaries) else len(lines)
        chunks.extend(
            _windows(
                commit_sha,
                path,
                lines,
                start,
                end,
                ChunkKind.DOCUMENTATION,
                language,
                symbol=heading,
            )
        )
    return chunks


def _windows(
    commit_sha: str,
    path: str,
    lines: list[str],
    start: int,
    end: int,
    kind: ChunkKind,
    language: str | None,
    *,
    symbol: str | None,
) -> list[CodeChunk]:
    """Emit one chunk for a span, or overlapping windows when it is too long."""
    if end < start:
        return []
    span = end - start + 1
    if span <= MAX_CHUNK_LINES:
        chunk = _build(commit_sha, path, lines, start, end, kind, language, symbol)
        return [chunk] if chunk is not None else []

    chunks: list[CodeChunk] = []
    cursor = start
    while cursor <= end:
        window_end = min(cursor + WINDOW_LINES - 1, end)
        chunk = _build(commit_sha, path, lines, cursor, window_end, kind, language, symbol)
        if chunk is not None:
            chunks.append(chunk)
        if window_end == end:
            break
        cursor = window_end - WINDOW_OVERLAP + 1
    return chunks


def _build(
    commit_sha: str,
    path: str,
    lines: list[str],
    start: int,
    end: int,
    kind: ChunkKind,
    language: str | None,
    symbol: str | None,
) -> CodeChunk | None:
    text = "".join(lines[start - 1 : end])
    if not text.strip():
        return None
    return build_chunk(
        commit_sha=commit_sha,
        path=path,
        start_line=start,
        end_line=end,
        text=text,
        kind=kind,
        chunker_version=CHUNKER_VERSION,
        symbol=symbol,
        language=language,
    )


def _contiguous_ranges(numbers: list[int]) -> list[tuple[int, int]]:
    if not numbers:
        return []
    ranges: list[tuple[int, int]] = []
    start = previous = numbers[0]
    for number in numbers[1:]:
        if number == previous + 1:
            previous = number
            continue
        ranges.append((start, previous))
        start = previous = number
    ranges.append((start, previous))
    return ranges
