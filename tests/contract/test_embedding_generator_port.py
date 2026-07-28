"""Contract suite for EmbeddingGeneratorPort (Ollama adapter joins in v0.1,
marked ``ollama``)."""

from __future__ import annotations

import math

import pytest

from issuepilot.knowledge.application.ports import EmbeddingGeneratorPort
from tests.support.fakes.embeddings import FakeEmbedder


@pytest.fixture(params=["fake"])
def embedder(request: pytest.FixtureRequest) -> EmbeddingGeneratorPort:
    return FakeEmbedder(dimension=8)


def test_vectors_match_declared_dimension(embedder: EmbeddingGeneratorPort) -> None:
    vectors = embedder.embed(["hello", "world"])
    assert all(len(v) == embedder.dimension for v in vectors)


def test_batch_preserves_order_and_length(embedder: EmbeddingGeneratorPort) -> None:
    texts = ["a", "b", "c"]
    vectors = embedder.embed(texts)
    assert len(vectors) == len(texts)
    assert vectors[0] == embedder.embed(["a"])[0]


def test_same_text_same_vector(embedder: EmbeddingGeneratorPort) -> None:
    first, second = embedder.embed(["stable"]), embedder.embed(["stable"])
    assert first == second


def test_vectors_are_unit_length(embedder: EmbeddingGeneratorPort) -> None:
    (vector,) = embedder.embed(["normalize me"])
    norm = math.sqrt(sum(x * x for x in vector))
    assert norm == pytest.approx(1.0, abs=1e-6)
