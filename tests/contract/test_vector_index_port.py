"""Contract suite for VectorIndexPort: fake and memory-mapped numpy index."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from issuepilot.knowledge.application.ports import VectorIndexPort
from issuepilot.knowledge.infrastructure.numpy_vectors import NumpyVectorIndex
from tests.support.fakes.knowledge import InMemoryVectorIndex

SHA = "a" * 40
OTHER_SHA = "b" * 40


def unit(*values: float) -> tuple[float, ...]:
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return tuple(v / norm for v in values)


@pytest.fixture(
    params=[
        pytest.param("fake", id="fake"),
        pytest.param("numpy", id="real", marks=pytest.mark.integration),
    ]
)
def index(request: pytest.FixtureRequest, tmp_path: Path) -> VectorIndexPort:
    if request.param == "fake":
        return InMemoryVectorIndex()
    return NumpyVectorIndex(tmp_path / "vectors")


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


def test_added_batches_accumulate(index: VectorIndexPort) -> None:
    index.add(SHA, [("first", unit(1.0, 0.0))])
    index.add(SHA, [("second", unit(0.0, 1.0))])
    assert set(index.search(SHA, unit(1.0, 1.0), limit=10)) == {"first", "second"}


def test_query_of_wrong_dimension_returns_nothing(index: VectorIndexPort) -> None:
    """A query embedded by a different model is not comparable; an empty
    result beats a confidently wrong ranking."""
    index.add(SHA, [("a", unit(1.0, 0.0))])
    assert list(index.search(SHA, unit(1.0, 0.0, 0.0), limit=5)) == []


def test_adding_nothing_is_a_no_op(index: VectorIndexPort) -> None:
    index.add(SHA, [])
    assert list(index.search(SHA, unit(1.0, 0.0), limit=5)) == []
