"""Ports required by evaluation use cases."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from issuepilot.evaluation.domain.case import EvaluationCase, EvaluationDataset
from issuepilot.evaluation.domain.scoring import ScoredReport


class DatasetPort(Protocol):
    def load(self, name: str) -> EvaluationDataset: ...

    def available(self) -> Sequence[str]: ...


class InvestigationRunnerPort(Protocol):
    """Runs one case and returns just enough of the report to score it.

    Deliberately narrow: evaluation must not depend on the investigation
    context's DTOs, or the two could not evolve independently.
    """

    def run_case(self, case: EvaluationCase) -> ScoredReport: ...


@dataclass(frozen=True, slots=True)
class TrackedRun:
    """One experiment run's lineage and results, tracker-agnostic."""

    name: str
    params: Mapping[str, str]
    metrics: Mapping[str, float]


class ExperimentTrackerPort(Protocol):
    """MLflow-shaped, MLflow-free: the CI default is a local fake."""

    def log_run(self, run: TrackedRun) -> None: ...
