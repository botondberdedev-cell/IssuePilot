"""Contract suite for ChunkStorePort."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from issuepilot.adapters.sqlite.connection import connect
from issuepilot.adapters.sqlite.migrator import migrate
from issuepilot.knowledge.application.ports import ChunkStorePort
from issuepilot.knowledge.domain.chunk import CodeChunk, build_chunk
from issuepilot.knowledge.domain.values import ChunkKind
from issuepilot.knowledge.infrastructure.chunk_repo import SqliteChunkStore
from tests.support.fakes.knowledge import InMemoryChunkStore

SHA = "a" * 40
OTHER_SHA = "b" * 40


def chunk(path: str, *, commit: str = SHA, symbol: str | None = None) -> CodeChunk:
    return build_chunk(
        commit_sha=commit,
        path=path,
        start_line=1,
        end_line=2,
        text=f"content of {path}\nsecond line\n",
        kind=ChunkKind.CODE,
        chunker_version="1",
        symbol=symbol,
        language="Python",
    )


@pytest.fixture(
    params=[
        pytest.param("fake", id="fake"),
        pytest.param("sqlite", id="real", marks=pytest.mark.integration),
    ]
)
def store(request: pytest.FixtureRequest) -> Iterator[ChunkStorePort]:
    if request.param == "fake":
        yield InMemoryChunkStore()
        return
    connection = connect(":memory:")
    try:
        migrate(connection)
        yield SqliteChunkStore(connection)
    finally:
        connection.close()


def test_put_then_get_roundtrip(store: ChunkStorePort) -> None:
    original = chunk("src/app.py", symbol="main")
    store.put_many([original])
    assert store.get(original.chunk_id) == original


def test_get_missing_returns_none(store: ChunkStorePort) -> None:
    assert store.get("nope") is None


def test_put_is_idempotent(store: ChunkStorePort) -> None:
    original = chunk("src/app.py")
    store.put_many([original, original])
    assert store.count_for_commit(SHA) == 1


def test_get_many_preserves_requested_order(store: ChunkStorePort) -> None:
    a, b = chunk("src/a.py"), chunk("src/b.py")
    store.put_many([a, b])
    assert [c.chunk_id for c in store.get_many([b.chunk_id, a.chunk_id])] == [
        b.chunk_id,
        a.chunk_id,
    ]


def test_get_many_omits_unknown_ids(store: ChunkStorePort) -> None:
    a = chunk("src/a.py")
    store.put_many([a])
    assert [c.chunk_id for c in store.get_many([a.chunk_id, "missing"])] == [a.chunk_id]


def test_get_many_of_nothing_is_empty(store: ChunkStorePort) -> None:
    assert store.get_many([]) == []


def test_count_is_scoped_to_a_commit(store: ChunkStorePort) -> None:
    store.put_many([chunk("src/a.py"), chunk("src/b.py"), chunk("src/c.py", commit=OTHER_SHA)])
    assert store.count_for_commit(SHA) == 2
    assert store.count_for_commit(OTHER_SHA) == 1


def test_delete_is_scoped_to_a_commit(store: ChunkStorePort) -> None:
    store.put_many([chunk("src/a.py"), chunk("src/c.py", commit=OTHER_SHA)])
    store.delete_for_commit(SHA)
    assert store.count_for_commit(SHA) == 0
    assert store.count_for_commit(OTHER_SHA) == 1


def test_all_fields_survive_a_roundtrip(store: ChunkStorePort) -> None:
    original = chunk("src/app.py", symbol="main")
    store.put_many([original])
    loaded = store.get(original.chunk_id)
    assert loaded is not None
    assert loaded.symbol == "main"
    assert loaded.language == "Python"
    assert loaded.kind is ChunkKind.CODE
    assert loaded.content_hash == original.content_hash
