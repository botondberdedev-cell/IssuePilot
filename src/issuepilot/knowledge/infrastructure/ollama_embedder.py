"""Embeddings via Ollama.

Vectors are re-normalized on arrival. Ollama already returns unit-length
vectors, but dot-product search *depends* on that being true, and a silent
change upstream would degrade ranking with nothing to catch it. Normalizing
costs almost nothing and makes the invariant ours rather than borrowed.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from issuepilot.adapters.ollama.client import OllamaClient
from issuepilot.shared_kernel.errors import ModelUnavailableError

_BATCH_SIZE = 64


class OllamaEmbedder:
    def __init__(self, client: OllamaClient, model: str) -> None:
        self._client = client
        self._model = model
        self._dimension: int | None = None

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            self.embed(["dimension probe"])
        if self._dimension is None:  # pragma: no cover - embed always sets it
            raise ModelUnavailableError(f"could not determine dimension of {self._model!r}")
        return self._dimension

    def embed(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        if not texts:
            return []
        vectors: list[tuple[float, ...]] = []
        for start in range(0, len(texts), _BATCH_SIZE):
            batch = list(texts[start : start + _BATCH_SIZE])
            vectors.extend(self._client.embed(self._model, batch))

        dimensions = {len(v) for v in vectors}
        if len(dimensions) > 1:
            raise ModelUnavailableError(
                f"embedding model {self._model!r} returned mixed dimensions {sorted(dimensions)}",
                remediation="re-pull the model; a mixed-dimension index cannot be searched",
            )
        if dimensions:
            self._dimension = dimensions.pop()
        return [_normalize(v) for v in vectors]


def _normalize(vector: tuple[float, ...]) -> tuple[float, ...]:
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0.0:
        return vector
    return tuple(x / norm for x in vector)
