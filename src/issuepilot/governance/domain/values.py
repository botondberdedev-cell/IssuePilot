"""Governance-context value objects."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, unique


@unique
class TaskClass(Enum):
    """The classes of model work that routing decides between."""

    CHAT = "chat"
    EMBEDDING = "embedding"
    SUMMARIZE = "summarize"


@dataclass(frozen=True, slots=True)
class ModelReference:
    """A model name as known to the local runtime (digest pinning in v0.2)."""

    name: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("model reference is empty")
