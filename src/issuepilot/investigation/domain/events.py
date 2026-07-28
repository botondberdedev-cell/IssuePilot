"""Investigation-context domain events."""

from __future__ import annotations

from dataclasses import dataclass

from issuepilot.shared_kernel.events import DomainEvent


@dataclass(frozen=True, slots=True, kw_only=True)
class InvestigationStarted(DomainEvent):
    run_id: str
    snapshot_sha: str


@dataclass(frozen=True, slots=True, kw_only=True)
class InvestigationCompleted(DomainEvent):
    run_id: str
    report_id: str
    finding_count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class InvestigationFailed(DomainEvent):
    run_id: str
    reason_category: str
