"""Contract suite for EmbeddingGeneratorPort.

The ``ollama``-marked parameter runs against a live daemon with the pinned
model. It is not part of the merge gate — a laptop without Ollama must still
be able to develop — but it is what proves the real model satisfies the same
contract the fake promises.
"""

from __future__ import annotations

import math

import pytest

from issuepilot.adapters.ollama.client import OllamaClient
from issuepilot.knowledge.application.ports import EmbeddingGeneratorPort
from issuepilot.knowledge.infrastructure.ollama_embedder import OllamaEmbedder
from tests.support.fakes.embeddings import FakeEmbedder

OLLAMA_URL = "http://127.0.0.1:11434"
EMBEDDING_MODEL = "embeddinggemma"


@pytest.fixture(
    params=[
        pytest.param("fake", id="fake"),
        pytest.param("ollama", id="real", marks=pytest.mark.ollama),
    ]
)
def embedder(request: pytest.FixtureRequest) -> EmbeddingGeneratorPort:
    if request.param == "fake":
        return FakeEmbedder(dimension=8)
    return OllamaEmbedder(OllamaClient(OLLAMA_URL), EMBEDDING_MODEL)


def test_reports_a_model_name(embedder: EmbeddingGeneratorPort) -> None:
    assert embedder.model_name


def test_vectors_match_declared_dimension(embedder: EmbeddingGeneratorPort) -> None:
    vectors = embedder.embed(["hello", "world"])
    assert all(len(v) == embedder.dimension for v in vectors)


def test_batch_preserves_order_and_length(embedder: EmbeddingGeneratorPort) -> None:
    texts = ["alpha", "bravo", "charlie"]
    vectors = embedder.embed(texts)
    assert len(vectors) == len(texts)
    assert vectors[0] == pytest.approx(embedder.embed(["alpha"])[0], abs=1e-5)


def test_same_text_same_vector(embedder: EmbeddingGeneratorPort) -> None:
    first, second = embedder.embed(["stable"]), embedder.embed(["stable"])
    assert first[0] == pytest.approx(second[0], abs=1e-6)


def test_vectors_are_unit_length(embedder: EmbeddingGeneratorPort) -> None:
    """Dot-product search is only cosine similarity if this holds."""
    for vector in embedder.embed(["normalize me", "and me too"]):
        assert math.sqrt(sum(x * x for x in vector)) == pytest.approx(1.0, abs=1e-5)


def test_embedding_nothing_returns_nothing(embedder: EmbeddingGeneratorPort) -> None:
    assert embedder.embed([]) == []


def test_related_text_scores_above_unrelated(embedder: EmbeddingGeneratorPort) -> None:
    """The property retrieval actually depends on. The fake is hash-based and
    carries no semantics, so this is a real-model check only."""
    if isinstance(embedder, FakeEmbedder):
        pytest.skip("hash-based fake carries no semantics")
    anchor, related, unrelated = embedder.embed(
        [
            "the function that handles a refund webhook retry",
            "def handle_retry(event): process the refund webhook again",
            "a recipe for sourdough bread with a long fermentation",
        ]
    )
    similarity_related = sum(a * b for a, b in zip(anchor, related, strict=True))
    similarity_unrelated = sum(a * b for a, b in zip(anchor, unrelated, strict=True))
    assert similarity_related > similarity_unrelated
