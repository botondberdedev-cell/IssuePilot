"""Contract suite for LexicalIndexPort: fake and real FTS5 must agree."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from issuepilot.adapters.sqlite.connection import connect
from issuepilot.adapters.sqlite.migrator import migrate
from issuepilot.knowledge.application.ports import LexicalIndexPort
from issuepilot.knowledge.domain.chunk import CodeChunk, build_chunk
from issuepilot.knowledge.domain.values import ChunkKind
from issuepilot.knowledge.infrastructure.fts5_index import Fts5LexicalIndex
from tests.support.fakes.knowledge import InMemoryLexicalIndex

SHA = "a" * 40
OTHER_SHA = "b" * 40


def chunk(path: str, text: str, *, commit: str = SHA, symbol: str | None = None) -> CodeChunk:
    return build_chunk(
        commit_sha=commit,
        path=path,
        start_line=1,
        end_line=text.count("\n") + 1,
        text=text,
        kind=ChunkKind.CODE,
        chunker_version="1",
        symbol=symbol,
    )


@pytest.fixture(
    params=[
        pytest.param("fake", id="fake"),
        pytest.param("fts5", id="real", marks=pytest.mark.integration),
    ]
)
def index(request: pytest.FixtureRequest) -> Iterator[LexicalIndexPort]:
    if request.param == "fake":
        yield InMemoryLexicalIndex()
        return
    connection = connect(":memory:")
    try:
        migrate(connection)
        yield Fts5LexicalIndex(connection)
    finally:
        connection.close()


@pytest.fixture
def populated(index: LexicalIndexPort) -> LexicalIndexPort:
    index.index(
        [
            chunk(
                "src/refunds/webhook.py",
                "def handle_retry(event):\n    deduplicate(event)\n",
                symbol="handle_retry",
            ),
            chunk(
                "src/refunds/state.py",
                "def transition(event):\n    settle(event)\n",
                symbol="transition",
            ),
            chunk("README.md", "# Payments\n\nHandles refunds.\n"),
            chunk("other/thing.py", "def unrelated():\n    pass\n", commit=OTHER_SHA),
        ]
    )
    return index


def test_finds_a_matching_term(populated: LexicalIndexPort) -> None:
    assert populated.search(SHA, "handle_retry", limit=10)


def test_results_are_scoped_to_the_commit(populated: LexicalIndexPort) -> None:
    """A hit from another snapshot must never surface: it could be cited."""
    hits = populated.search(SHA, "unrelated", limit=10)
    assert hits == []


def test_no_match_returns_empty(populated: LexicalIndexPort) -> None:
    assert populated.search(SHA, "zzzznotpresent", limit=10) == []


def test_limit_is_respected(populated: LexicalIndexPort) -> None:
    assert len(populated.search(SHA, "event refunds", limit=1)) <= 1


def test_empty_query_returns_empty(populated: LexicalIndexPort) -> None:
    assert populated.search(SHA, "   ", limit=10) == []


def test_clear_removes_only_that_commit(populated: LexicalIndexPort) -> None:
    populated.clear(SHA)
    assert populated.search(SHA, "handle_retry", limit=10) == []
    assert populated.search(OTHER_SHA, "unrelated", limit=10)


def test_snake_case_identifiers_are_searchable_whole(populated: LexicalIndexPort) -> None:
    assert populated.search(SHA, "handle_retry", limit=10)


@pytest.mark.parametrize(
    "hostile",
    [
        'foo" OR "',
        "NOT everything",
        "text:secret",
        "(unbalanced",
        "*",
        "^caret",
        "a AND b OR NOT c",
        '"',
    ],
)
def test_query_syntax_cannot_be_injected(populated: LexicalIndexPort, hostile: str) -> None:
    """Query text comes from the issue statement and from model tool calls;
    FTS5 operators in it must be treated as literal terms, not syntax."""
    results = populated.search(SHA, hostile, limit=10)
    assert isinstance(list(results), list)  # must not raise
