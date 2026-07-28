"""Governance-context domain events."""

from __future__ import annotations

from dataclasses import dataclass

from issuepilot.shared_kernel.events import DomainEvent


@dataclass(frozen=True, slots=True, kw_only=True)
class ChampionConfigurationChanged(DomainEvent):
    task_class: str
    previous_model: str
    new_model: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PolicyDenialRecorded(DomainEvent):
    policy_name: str
    denied_operation: str
