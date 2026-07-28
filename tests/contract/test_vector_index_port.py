"""Contract suite for VectorIndexPort (the numpy adapter joins in v0.1-2b)."""

from __future__ import annotations

import math

import pytest

from issuepilot.knowledge.application.ports import VectorIndexPort
from tests.support.fakes.knowledge import InMemoryVectorIndex

SHA = "a" * 40
OTHER_SHA = "b" * 40


def unit(*values: float) -> tuple[float, ...]:
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return tuple(v / norm for v in values)


@pytest.fixture(params=["fake"])
def index(request: pytest.FixtureRequest) -> VectorIndexPort:
    return InMemoryVectorIndex()


@pytest.fixture
def populated(index: VectorIndexPort) -> VectorIndexPort:
    index.add(
        SHA,
        [("north", unit(0.0, 1.0)), ("east", unit(1.0, 0.0)), ("northeast", unit(1.0, 1.0))],
    )
    index.add(OTHER_SHA, [("elsewhere", unit(0.0, 1.0))])
    return index


def test_nearest_vector_ranks_first(populated: VectorIndexPort) -> None:
    assert next(iter(populated.search(SHA, unit(0.0, 1.0), limit=3))) == "north"


def test_results_are_scoped_to_the_commit(populated: VectorIndexPort) -> None:
    assert "elsewhere" not in populated.search(SHA, unit(0.0, 1.0), limit=10)


def test_limit_is_respected(populated: VectorIndexPort) -> None:
    assert len(populated.search(SHA, unit(1.0, 1.0), limit=2)) == 2


def test_ordering_follows_similarity(populated: VectorIndexPort) -> None:
    ranked = list(populated.search(SHA, unit(1.0, 0.0), limit=3))
    assert ranked[0] == "east"
    assert ranked.index("northeast") < ranked.index("north")


def test_empty_index_returns_empty(index: VectorIndexPort) -> None:
    assert list(index.search(SHA, unit(1.0, 0.0), limit=5)) == []


def test_clear_removes_only_that_commit(populated: VectorIndexPort) -> None:
    populated.clear(SHA)
    assert list(populated.search(SHA, unit(0.0, 1.0), limit=5)) == []
    assert list(populated.search(OTHER_SHA, unit(0.0, 1.0), limit=5)) == ["elsewhere"]
