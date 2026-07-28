"""Deterministic model routing (v0.1: a config-pinned decision table)."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

from issuepilot.governance.domain.values import ModelReference, TaskClass

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass(frozen=True, slots=True)
class RoutingTable:
    """Total mapping from task class to model — no fallthrough, no default."""

    entries: Mapping[TaskClass, ModelReference]

    def __post_init__(self) -> None:
        missing = set(TaskClass) - set(self.entries)
        if missing:
            names = ", ".join(sorted(t.value for t in missing))
            raise ValueError(f"routing table is not total; missing: {names}")
        object.__setattr__(self, "entries", MappingProxyType(dict(self.entries)))

    def route(self, task: TaskClass) -> ModelReference:
        return self.entries[task]
