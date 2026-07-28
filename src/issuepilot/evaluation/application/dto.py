"""Immutable DTOs crossing the evaluation context's boundary.

These carry plain data, never domain objects. That is what lets the CLI
render a suite result without importing evaluation's domain — the boundary
the architecture contract enforces.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class CaseScoreDTO:
    case_id: str
    category: str
    passed: bool
    metrics: Mapping[str, float]

    def __post_init__(self) -> None:
        object.__setattr__(self, "metrics", MappingProxyType(dict(self.metrics)))

    def weak_metrics(self) -> tuple[str, ...]:
        return tuple(name for name, value in self.metrics.items() if value < 1.0)


@dataclass(frozen=True, slots=True)
class ThresholdResultDTO:
    metric: str
    required: float
    actual: float | None
    met: bool
    mandatory: bool

    def describe(self) -> str:
        if self.actual is None:
            return f"{self.metric}: MISSING (required >= {self.required:.2f})"
        verdict = "ok" if self.met else "FAIL"
        return f"{self.metric}: {self.actual:.3f} (required >= {self.required:.2f}) {verdict}"


@dataclass(frozen=True, slots=True)
class SuiteResultDTO:
    evaluation_run_id: str
    dataset: str
    dataset_hash: str
    passed: bool
    metrics: Mapping[str, float]
    thresholds: tuple[ThresholdResultDTO, ...]
    cases: tuple[CaseScoreDTO, ...]
    errors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "metrics", MappingProxyType(dict(self.metrics)))

    @property
    def failing_cases(self) -> tuple[CaseScoreDTO, ...]:
        return tuple(case for case in self.cases if not case.passed)

    @property
    def blocking_metrics(self) -> tuple[str, ...]:
        return tuple(t.metric for t in self.thresholds if t.mandatory and not t.met)
