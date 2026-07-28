"""Evaluation-context domain events."""

from __future__ import annotations

from dataclasses import dataclass

from issuepilot.shared_kernel.events import DomainEvent


@dataclass(frozen=True, slots=True, kw_only=True)
class EvaluationCompleted(DomainEvent):
    evaluation_run_id: str
    case_count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class QualityGateFailed(DomainEvent):
    evaluation_run_id: str
    gate_name: str
