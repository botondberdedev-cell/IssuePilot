"""Quality gates.

A gate turns metrics into a merge/no-merge decision. Two rules make it
trustworthy:

*Safety thresholds are absolute.* A metric marked mandatory must be met
outright — a latency win cannot buy back a citation that pointed at the wrong
snapshot.

*A missing metric fails.* If the suite did not produce a number the gate
requires, the gate does not pass on the grounds that nothing said otherwise.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum, unique


@unique
class GateOutcome(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class Threshold:
    metric: str
    minimum: float
    mandatory: bool = True

    def __post_init__(self) -> None:
        if not 0.0 <= self.minimum <= 1.0:
            raise ValueError(f"threshold for {self.metric} must be within [0, 1]")


@dataclass(frozen=True, slots=True)
class ThresholdResult:
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
class GateVerdict:
    outcome: GateOutcome
    results: tuple[ThresholdResult, ...]

    @property
    def passed(self) -> bool:
        return self.outcome is GateOutcome.PASSED

    @property
    def failures(self) -> tuple[ThresholdResult, ...]:
        return tuple(r for r in self.results if not r.met)

    def summary(self) -> str:
        return "\n".join(result.describe() for result in self.results)


@dataclass(frozen=True, slots=True)
class QualityGate:
    name: str
    thresholds: tuple[Threshold, ...]

    def __post_init__(self) -> None:
        if not self.thresholds:
            raise ValueError("a gate with no thresholds would pass anything")

    def evaluate(self, metrics: Mapping[str, float]) -> GateVerdict:
        results: list[ThresholdResult] = []
        for threshold in self.thresholds:
            actual = metrics.get(threshold.metric)
            # A metric the suite never produced counts as unmet, not as absent
            # evidence of a problem.
            met = actual is not None and actual >= threshold.minimum
            results.append(
                ThresholdResult(
                    metric=threshold.metric,
                    required=threshold.minimum,
                    actual=actual,
                    met=met,
                    mandatory=threshold.mandatory,
                )
            )
        failed_mandatory = any(r.mandatory and not r.met for r in results)
        return GateVerdict(
            outcome=GateOutcome.FAILED if failed_mandatory else GateOutcome.PASSED,
            results=tuple(results),
        )


DEFAULT_GATE = QualityGate(
    name="v0.1-baseline",
    thresholds=(
        # Absolute: a citation that does not resolve in the run's own snapshot
        # is the one failure this product cannot ship.
        Threshold(metric="citation-validity", minimum=1.0),
        Threshold(metric="forbidden-claim-absence", minimum=1.0),
        Threshold(metric="honesty", minimum=1.0),
        # Retrieval quality: a baseline to regress against, not a ceiling.
        Threshold(metric="required-path-recall", minimum=0.6),
        Threshold(metric="pass-rate", minimum=0.5),
        Threshold(metric="claim-grounding", minimum=0.7, mandatory=False),
    ),
)
