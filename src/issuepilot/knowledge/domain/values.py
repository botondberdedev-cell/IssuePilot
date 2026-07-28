"""Knowledge-context value objects."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, unique


@unique
class ChunkKind(Enum):
    CODE = "code"
    DOCUMENTATION = "documentation"
    CONFIGURATION = "configuration"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class Query:
    """A retrieval query; always non-empty after trimming."""

    text: str

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("retrieval query is empty")


@dataclass(frozen=True, slots=True)
class RetrievalScore:
    """A non-negative relevance score; per-source ranks stay interpretable."""

    value: float

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError(f"retrieval score must be non-negative, got {self.value}")
