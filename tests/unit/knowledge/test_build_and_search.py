"""Index building and hybrid search, driven through fakes."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from issuepilot.knowledge.application.use_cases.build_index import (
    BuildIndex,
    BuildIndexCommand,
)
from issuepilot.knowledge.application.use_cases.search import Search, SearchCommand
from issuepilot.knowledge.domain.events import KnowledgeIndexReady
from issuepilot.shared_kernel.cancellation import CancellationToken
from issuepilot.shared_kernel.clock import FixedClock
from issuepilot.shared_kernel.errors import OperationInterruptedError
from issuepilot.shared_kernel.ids import UlidGenerator
from tests.support.fakes.embeddings import FakeEmbedder
from tests.support.fakes.eventbus import RecordingEventBus
from tests.support.fakes.knowledge import (
    FakeSource,
    InMemoryChunkStore,
    InMemoryLexicalIndex,
    InMemoryVectorIndex,
)

SHA = "a" * 40


class Harness:
    def __init__(self) -> None:
        self.source = FakeSource()
        self.chunks = InMemoryChunkStore()
        self.lexical = InMemoryLexicalIndex()
        self.vectors = InMemoryVectorIndex()
        self.embedder = FakeEmbedder()
        self.bus = RecordingEventBus()
        self.build = BuildIndex(
            source=self.source,
            chunks=self.chunks,
            lexical=self.lexical,
            ids=UlidGenerator(),
            clock=FixedClock(datetime(2026, 7, 28, tzinfo=UTC)),
            bus=self.bus,
        )

    def searcher(self, *, semantic: bool = False) -> Search:
        return Search(
            chunks=self.chunks,
            lexical=self.lexical,
            vectors=self.vectors if semantic else None,
            embedder=self.embedder if semantic else None,
        )


@pytest.fixture
def harness() -> Harness:
    h = Harness()
    h.source.add(
        "src/refunds/webhook.py",
        "def handle_retry(event):\n    if duplicate(event):\n        return\n",
        "Python",
    )
    h.source.add("src/refunds/state.py", "def transition(event):\n    settle(event)\n", "Python")
    h.source.add("README.md", "# Payments\n\nRefund handling.\n", "Markdown")
    return h


class TestBuildIndex:
    def test_indexes_every_eligible_file(self, harness: Harness) -> None:
        stats = harness.build.execute(BuildIndexCommand(SHA))
        assert stats.indexed_files == 3
        assert stats.chunk_count > 0
        assert harness.chunks.count_for_commit(SHA) == stats.chunk_count

    def test_publishes_a_ready_event(self, harness: Harness) -> None:
        harness.build.execute(BuildIndexCommand(SHA))
        (event,) = harness.bus.published
        assert isinstance(event, KnowledgeIndexReady)
        assert event.snapshot_sha == SHA

    def test_rebuild_replaces_rather_than_accumulates(self, harness: Harness) -> None:
        first = harness.build.execute(BuildIndexCommand(SHA))
        second = harness.build.execute(BuildIndexCommand(SHA))
        assert second.chunk_count == first.chunk_count
        assert harness.chunks.count_for_commit(SHA) == first.chunk_count

    def test_empty_files_are_skipped(self) -> None:
        harness = Harness()
        harness.source.add("empty.py", "\n\n", "Python")
        stats = harness.build.execute(BuildIndexCommand(SHA))
        assert stats.indexed_files == 0
        assert stats.chunk_count == 0

    def test_cancellation_stops_the_build(self, harness: Harness) -> None:
        token = CancellationToken()
        token.cancel()
        with pytest.raises(OperationInterruptedError):
            harness.build.execute(BuildIndexCommand(SHA), cancellation=token)


class TestSearch:
    def test_lexical_search_finds_the_relevant_chunk(self, harness: Harness) -> None:
        harness.build.execute(BuildIndexCommand(SHA))
        hits = harness.searcher().execute(SearchCommand(commit_sha=SHA, query="handle_retry"))
        assert hits
        assert hits[0].path == "src/refunds/webhook.py"

    def test_hits_carry_citable_coordinates(self, harness: Harness) -> None:
        harness.build.execute(BuildIndexCommand(SHA))
        (hit, *_) = harness.searcher().execute(SearchCommand(commit_sha=SHA, query="handle_retry"))
        assert hit.commit_sha == SHA
        assert hit.start_line >= 1
        assert hit.end_line >= hit.start_line
        assert hit.snippet

    def test_search_works_without_any_embedding_model(self, harness: Harness) -> None:
        harness.build.execute(BuildIndexCommand(SHA))
        searcher = harness.searcher(semantic=False)
        assert not searcher.has_semantic
        assert searcher.execute(SearchCommand(commit_sha=SHA, query="transition"))

    def test_sources_are_attributed(self, harness: Harness) -> None:
        harness.build.execute(BuildIndexCommand(SHA))
        (hit, *_) = harness.searcher().execute(SearchCommand(commit_sha=SHA, query="settle"))
        assert hit.sources == ("lexical",)

    def test_hybrid_search_attributes_both_retrievers(self, harness: Harness) -> None:
        harness.build.execute(BuildIndexCommand(SHA))
        stored = [harness.chunks.get(cid) for cid in _all_chunk_ids(harness)]
        harness.vectors.add(
            SHA,
            [(c.chunk_id, harness.embedder.embed([c.text])[0]) for c in stored if c is not None],
        )
        hits = harness.searcher(semantic=True).execute(
            SearchCommand(commit_sha=SHA, query="handle_retry")
        )
        assert hits
        assert any("semantic" in hit.sources for hit in hits)

    def test_empty_query_returns_nothing(self, harness: Harness) -> None:
        harness.build.execute(BuildIndexCommand(SHA))
        assert harness.searcher().execute(SearchCommand(commit_sha=SHA, query="  ")) == []

    def test_results_never_cross_snapshots(self, harness: Harness) -> None:
        harness.build.execute(BuildIndexCommand(SHA))
        assert (
            harness.searcher().execute(SearchCommand(commit_sha="b" * 40, query="handle_retry"))
            == []
        )

    def test_limit_is_respected(self, harness: Harness) -> None:
        harness.build.execute(BuildIndexCommand(SHA))
        hits = harness.searcher().execute(
            SearchCommand(commit_sha=SHA, query="event refunds payments", limit=1)
        )
        assert len(hits) <= 1


def _all_chunk_ids(harness: Harness) -> list[str]:
    return list(harness.lexical.search(SHA, "def refunds payments", limit=100))
