"""Drift detection over metric windows.

Two things get conflated in practice and are kept apart here:

*Data drift* — the inputs changed. Detectable from inputs alone.

*Concept drift* — the relationship between inputs and correct outputs
changed. **Not** detectable without outcome labels. When labels are missing
this module says so rather than reporting "no drift", because silence and
absence of evidence are different answers.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum, unique


@unique
class DriftVerdict(StrEnum):
    STABLE = "stable"
    DATA_DRIFT = "data-drift"
    CONCEPT_DRIFT_SUSPECTED = "concept-drift-suspected"
    INSUFFICIENT_DATA = "insufficient-data"
    """Not a clean bill of health — there was not enough to judge."""


@dataclass(frozen=True, slots=True)
class Window:
    """A sample of a metric, optionally with outcome labels."""

    name: str
    values: tuple[float, ...]
    accuracy: float | None = None
    """Fraction of outcomes judged correct, when labels exist."""

    @property
    def size(self) -> int:
        return len(self.values)

    def mean(self) -> float:
        return sum(self.values) / self.size if self.values else 0.0

    def stdev(self) -> float:
        if self.size < 2:
            return 0.0
        average = self.mean()
        variance = sum((v - average) ** 2 for v in self.values) / (self.size - 1)
        return math.sqrt(variance)


@dataclass(frozen=True, slots=True)
class DriftReport:
    verdict: DriftVerdict
    effect_size: float
    baseline_mean: float
    current_mean: float
    detail: str

    @property
    def drifted(self) -> bool:
        return self.verdict in (DriftVerdict.DATA_DRIFT, DriftVerdict.CONCEPT_DRIFT_SUSPECTED)


MIN_WINDOW = 5
DEFAULT_EFFECT_THRESHOLD = 0.5
"""Cohen's d of 0.5 — a medium effect. Below this, a shift in a small local
sample is not worth acting on."""

DEFAULT_ACCURACY_DROP = 0.1


def classify(
    baseline: Window,
    current: Window,
    *,
    effect_threshold: float = DEFAULT_EFFECT_THRESHOLD,
    accuracy_drop: float = DEFAULT_ACCURACY_DROP,
) -> DriftReport:
    if baseline.size < MIN_WINDOW or current.size < MIN_WINDOW:
        return DriftReport(
            verdict=DriftVerdict.INSUFFICIENT_DATA,
            effect_size=0.0,
            baseline_mean=baseline.mean(),
            current_mean=current.mean(),
            detail=(
                f"need at least {MIN_WINDOW} samples per window; "
                f"have {baseline.size} and {current.size}"
            ),
        )

    effect = _cohens_d(baseline, current)

    # Concept drift is only claimable with labels on both sides.
    if baseline.accuracy is not None and current.accuracy is not None:
        drop = baseline.accuracy - current.accuracy
        if drop > accuracy_drop:
            return DriftReport(
                verdict=DriftVerdict.CONCEPT_DRIFT_SUSPECTED,
                effect_size=effect,
                baseline_mean=baseline.mean(),
                current_mean=current.mean(),
                detail=(
                    f"accuracy fell {baseline.accuracy:.3f} -> {current.accuracy:.3f} "
                    f"({drop:.3f} > {accuracy_drop:.3f})"
                ),
            )

    if abs(effect) >= effect_threshold:
        labelled = baseline.accuracy is not None and current.accuracy is not None
        suffix = (
            "" if labelled else " (no outcome labels, so concept drift cannot be ruled in or out)"
        )
        return DriftReport(
            verdict=DriftVerdict.DATA_DRIFT,
            effect_size=effect,
            baseline_mean=baseline.mean(),
            current_mean=current.mean(),
            detail=f"effect size {effect:.2f} >= {effect_threshold:.2f}{suffix}",
        )

    return DriftReport(
        verdict=DriftVerdict.STABLE,
        effect_size=effect,
        baseline_mean=baseline.mean(),
        current_mean=current.mean(),
        detail=f"effect size {effect:.2f} below {effect_threshold:.2f}",
    )


def _cohens_d(baseline: Window, current: Window) -> float:
    """Standardized mean difference, using the pooled standard deviation."""
    pooled = math.sqrt((baseline.stdev() ** 2 + current.stdev() ** 2) / 2)
    if pooled == 0.0:
        return 0.0 if baseline.mean() == current.mean() else math.inf
    return (current.mean() - baseline.mean()) / pooled


def _sequence_mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0
