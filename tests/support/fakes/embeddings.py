from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence


class FakeEmbedder:
    """Deterministic hash-based unit vectors: same text, same embedding."""

    def __init__(self, dimension: int = 8, model_name: str = "fake-embedder") -> None:
        self._dimension = dimension
        self._model_name = model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> tuple[float, ...]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        raw = [
            int.from_bytes(digest[i * 4 : i * 4 + 4], "big") / 2**32 - 0.5
            for i in range(self._dimension)
        ]
        norm = math.sqrt(sum(x * x for x in raw)) or 1.0
        return tuple(x / norm for x in raw)
