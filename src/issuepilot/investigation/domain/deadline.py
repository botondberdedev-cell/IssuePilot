"""Wall-clock budget for an investigation.

The step budget bounds how many model calls happen; it says nothing about how
long they take. A model that has begun paging from disk can spend minutes on
a single call, so a run needs a deadline as well as a step count.

The deadline is a pure function of elapsed time, so it is testable without
sleeping — the clock is injected, never read directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from issuepilot.shared_kernel.errors import OperationInterruptedError


@dataclass(frozen=True, slots=True)
class Deadline:
    started_at: datetime
    limit: timedelta

    def __post_init__(self) -> None:
        if self.started_at.tzinfo is None:
            raise ValueError("a deadline requires an aware start time")
        if self.limit <= timedelta(0):
            raise ValueError(f"deadline must be positive, got {self.limit}")

    @classmethod
    def of_seconds(cls, started_at: datetime, seconds: float) -> Deadline:
        return cls(started_at=started_at, limit=timedelta(seconds=seconds))

    def expired(self, now: datetime) -> bool:
        return now - self.started_at >= self.limit

    def remaining(self, now: datetime) -> timedelta:
        left = self.limit - (now - self.started_at)
        return max(left, timedelta(0))

    def raise_if_expired(self, now: datetime) -> None:
        if self.expired(now):
            raise OperationInterruptedError(
                f"investigation exceeded its {self.limit.total_seconds():.0f}s budget",
                remediation=(
                    "raise investigation.timeout_seconds in issuepilot.toml, or lower --max-steps"
                ),
            )
