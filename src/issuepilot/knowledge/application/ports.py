"""Ports required by knowledge use cases (skeleton set; grows in v0.1)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class EmbeddingGeneratorPort(Protocol):
    """Batch text embedding. Returned vectors are unit-length."""

    @property
    def dimension(self) -> int: ...

    def embed(self, texts: Sequence[str]) -> list[tuple[float, ...]]: ...
