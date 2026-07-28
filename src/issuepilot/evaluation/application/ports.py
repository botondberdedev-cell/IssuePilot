"""Ports required by evaluation use cases (skeleton set; grows in v0.2)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class TrackedRun:
    """One experiment run's lineage and results, tracker-agnostic."""

    name: str
    params: Mapping[str, str]
    metrics: Mapping[str, float]


class ExperimentTrackerPort(Protocol):
    """MLflow-shaped, MLflow-free: the CI default is a local fake."""

    def log_run(self, run: TrackedRun) -> None: ...
