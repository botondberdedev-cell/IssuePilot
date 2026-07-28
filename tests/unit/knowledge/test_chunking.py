from __future__ import annotations

import pytest

from issuepilot.knowledge.domain.chunk import CodeChunk
from issuepilot.knowledge.domain.chunking import (
    MAX_CHUNK_LINES,
    WINDOW_LINES,
    chunk_document,
)
from issuepilot.knowledge.domain.values import ChunkKind

SHA = "a" * 40

PYTHON_SOURCE = '''"""Module docstring."""

import os

CONSTANT = 1


def first(x):
    return x + 1


@decorator
def second(y):
    """Docstring."""
    return y * 2


class Thing:
    def method(self):
        return None
'''


def chunk(
    text: str, *, path: str = "src/app.py", language: str | None = "Python"
) -> list[CodeChunk]:
    return chunk_document(commit_sha=SHA, path=path, text=text, language=language)


class TestPythonChunking:
    def test_top_level_definitions_become_chunks(self) -> None:
        symbols = {c.symbol for c in chunk(PYTHON_SOURCE)}
        assert {"first", "second", "Thing"} <= symbols

    def test_decorators_are_included_in_the_definition(self) -> None:
        (second,) = [c for c in chunk(PYTHON_SOURCE) if c.symbol == "second"]
        assert "@decorator" in second.text
        assert "def second" in second.text

    def test_module_preamble_is_retained(self) -> None:
        preamble = [c for c in chunk(PYTHON_SOURCE) if c.symbol is None]
        assert preamble
        combined = "".join(c.text for c in preamble)
        assert "import os" in combined
        assert "CONSTANT = 1" in combined

    def test_chunks_are_ordered_by_position(self) -> None:
        chunks = chunk(PYTHON_SOURCE)
        assert [c.start_line for c in chunks] == sorted(c.start_line for c in chunks)

    def test_unparseable_python_still_yields_chunks(self) -> None:
        chunks = chunk("def broken(:\n    this is not python\n")
        assert chunks
        assert all(c.text for c in chunks)

    def test_line_numbers_map_back_to_the_source(self) -> None:
        lines = PYTHON_SOURCE.splitlines(keepends=True)
        for produced in chunk(PYTHON_SOURCE):
            expected = "".join(lines[produced.start_line - 1 : produced.end_line])
            assert produced.text == expected


class TestMarkdownChunking:
    MARKDOWN = "Intro paragraph.\n\n# First\n\nBody one.\n\n## Second\n\nBody two.\n"

    def test_sections_split_on_headings(self) -> None:
        chunks = chunk(self.MARKDOWN, path="README.md", language="Markdown")
        assert [c.symbol for c in chunks] == [None, "First", "Second"]

    def test_content_before_the_first_heading_is_kept(self) -> None:
        chunks = chunk(self.MARKDOWN, path="README.md", language="Markdown")
        assert "Intro paragraph." in chunks[0].text

    def test_kind_is_documentation(self) -> None:
        chunks = chunk(self.MARKDOWN, path="README.md", language="Markdown")
        assert all(c.kind is ChunkKind.DOCUMENTATION for c in chunks)

    def test_markdown_without_headings_still_chunks(self) -> None:
        chunks = chunk("just text\n", path="README.md", language="Markdown")
        assert len(chunks) == 1


class TestWindowing:
    def test_long_span_is_split_into_windows(self) -> None:
        text = "".join(f"line {i}\n" for i in range(1, MAX_CHUNK_LINES + 200))
        chunks = chunk(text, path="data.txt", language=None)
        assert len(chunks) > 1
        assert all(c.line_count <= WINDOW_LINES for c in chunks)

    def test_windows_overlap_so_boundaries_are_not_lost(self) -> None:
        text = "".join(f"line {i}\n" for i in range(1, MAX_CHUNK_LINES + 200))
        chunks = chunk(text, path="data.txt", language=None)
        first, second = chunks[0], chunks[1]
        assert second.start_line <= first.end_line

    def test_windows_cover_the_whole_file(self) -> None:
        total = MAX_CHUNK_LINES + 200
        text = "".join(f"line {i}\n" for i in range(1, total))
        chunks = chunk(text, path="data.txt", language=None)
        assert chunks[0].start_line == 1
        assert chunks[-1].end_line == total - 1


class TestGeneralProperties:
    @pytest.mark.parametrize("empty", ["", "   ", "\n\n\n"])
    def test_empty_content_yields_no_chunks(self, empty: str) -> None:
        assert chunk(empty) == []

    def test_chunking_is_deterministic(self) -> None:
        first, second = chunk(PYTHON_SOURCE), chunk(PYTHON_SOURCE)
        assert [c.chunk_id for c in first] == [c.chunk_id for c in second]

    def test_chunk_ids_differ_across_commits(self) -> None:
        other = chunk_document(
            commit_sha="b" * 40, path="src/app.py", text=PYTHON_SOURCE, language="Python"
        )
        assert {c.chunk_id for c in chunk(PYTHON_SOURCE)}.isdisjoint({c.chunk_id for c in other})

    def test_chunk_ids_differ_across_paths(self) -> None:
        other = chunk(PYTHON_SOURCE, path="src/other.py")
        assert {c.chunk_id for c in chunk(PYTHON_SOURCE)}.isdisjoint({c.chunk_id for c in other})

    def test_no_chunk_is_blank(self) -> None:
        assert all(c.text.strip() for c in chunk(PYTHON_SOURCE))

    def test_config_files_are_marked_as_configuration(self) -> None:
        chunks = chunk("key: value\n", path="config.yml", language="YAML")
        assert all(c.kind is ChunkKind.CONFIGURATION for c in chunks)
