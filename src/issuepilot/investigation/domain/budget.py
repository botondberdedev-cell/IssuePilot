"""Investigation budgets.

Budgets are immutable; spending returns a new instance. The invariant that a
budget can never go negative is enforced here, not in strategy loops.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from issuepilot.shared_kernel.errors import IssuePilotError


class BudgetExhaustedError(IssuePilotError):
    """Raised when a strategy tries to spend past a budget's limit."""


@dataclass(frozen=True, slots=True)
class StepBudget:
    limit: int
    spent: int = 0

    def __post_init__(self) -> None:
        if self.limit < 1:
            raise ValueError(f"step budget limit must be positive, got {self.limit}")
        if not 0 <= self.spent <= self.limit:
            raise ValueError(f"spent {self.spent} outside [0, {self.limit}]")

    @property
    def remaining(self) -> int:
        return self.limit - self.spent

    @property
    def exhausted(self) -> bool:
        return self.remaining == 0

    def spend(self, steps: int = 1) -> StepBudget:
        if steps < 1:
            raise ValueError("must spend at least one step")
        if steps > self.remaining:
            raise BudgetExhaustedError(f"step budget exhausted ({self.spent}/{self.limit} spent)")
        return replace(self, spent=self.spent + steps)


@dataclass(frozen=True, slots=True)
class TokenBudget:
    limit: int
    spent: int = 0

    def __post_init__(self) -> None:
        if self.limit < 1:
            raise ValueError(f"token budget limit must be positive, got {self.limit}")
        if not 0 <= self.spent <= self.limit:
            raise ValueError(f"spent {self.spent} outside [0, {self.limit}]")

    @property
    def remaining(self) -> int:
        return self.limit - self.spent

    @property
    def exhausted(self) -> bool:
        return self.remaining == 0

    def spend(self, tokens: int) -> TokenBudget:
        if tokens < 0:
            raise ValueError("token spend cannot be negative")
        if tokens > self.remaining:
            raise BudgetExhaustedError(f"token budget exhausted ({self.spent}/{self.limit} spent)")
        return replace(self, spent=self.spent + tokens)


@dataclass(frozen=True, slots=True)
class DurationBudget:
    """Wall-clock budget; expiry is a pure function of elapsed seconds."""

    limit_seconds: float

    def __post_init__(self) -> None:
        if self.limit_seconds <= 0:
            raise ValueError(f"duration budget must be positive, got {self.limit_seconds}")

    def expired(self, elapsed_seconds: float) -> bool:
        return elapsed_seconds >= self.limit_seconds
