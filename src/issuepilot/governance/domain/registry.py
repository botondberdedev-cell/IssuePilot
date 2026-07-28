"""Champion and challenger configurations.

A champion is the configuration whose results a release stands behind.
Promotion is deliberately awkward: it requires evidence (a dataset hash and
the metrics that justified it), because a champion promoted on a hunch is
indistinguishable from no champion at all.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum, unique
from types import MappingProxyType

from issuepilot.governance.domain.values import ModelReference, TaskClass


@unique
class Role(StrEnum):
    CHAMPION = "champion"
    CHALLENGER = "challenger"


@dataclass(frozen=True, slots=True)
class ConfigurationRecord:
    """One evaluated configuration, with the evidence behind it."""

    configuration_id: str
    task: TaskClass
    model: ModelReference
    role: Role
    dataset_hash: str
    metrics: Mapping[str, float] = field(default_factory=dict)
    promoted_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.configuration_id.strip():
            raise ValueError("a configuration record requires an id")
        if self.role is Role.CHAMPION:
            if not self.dataset_hash:
                raise ValueError("a champion must name the dataset that justified it")
            if self.promoted_at is None:
                raise ValueError("a champion must record when it was promoted")
        object.__setattr__(self, "metrics", MappingProxyType(dict(self.metrics)))


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    promoted: bool
    reasons: tuple[str, ...]

    def explain(self) -> str:
        return "; ".join(self.reasons) if self.reasons else "no reasons recorded"


# Metrics where any regression blocks promotion, however small. These are the
# properties a report's credibility rests on.
SAFETY_METRICS: frozenset[str] = frozenset(
    {"citation-validity", "forbidden-claim-absence", "honesty"}
)


def decide_promotion(
    champion: ConfigurationRecord | None,
    challenger: ConfigurationRecord,
    *,
    tolerance: float = 0.0,
) -> PromotionDecision:
    """Compare a challenger against the incumbent.

    Rules, in order of authority:

    1. The two must have been measured on the same dataset. Comparing across
       datasets is not a comparison.
    2. No safety metric may regress at all — tolerance does not apply to them.
    3. The overall pass rate must not fall by more than ``tolerance``.
    """
    if champion is None:
        return PromotionDecision(True, ("no incumbent champion",))

    if champion.dataset_hash != challenger.dataset_hash:
        return PromotionDecision(
            False, ("champion and challenger were measured on different datasets",)
        )

    regressions = [
        f"{metric} regressed {champion.metrics[metric]:.3f} -> {value:.3f}"
        for metric in sorted(SAFETY_METRICS)
        if (value := challenger.metrics.get(metric, 0.0)) < champion.metrics.get(metric, 0.0)
    ]
    if regressions:
        return PromotionDecision(False, tuple(regressions))

    champion_rate = champion.metrics.get("pass-rate", 0.0)
    challenger_rate = challenger.metrics.get("pass-rate", 0.0)
    if challenger_rate < champion_rate - tolerance:
        return PromotionDecision(
            False,
            (f"pass-rate fell {champion_rate:.3f} -> {challenger_rate:.3f}",),
        )

    return PromotionDecision(
        True, (f"pass-rate {champion_rate:.3f} -> {challenger_rate:.3f}, no safety regression",)
    )
