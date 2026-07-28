"""Feedback-context domain events."""

from __future__ import annotations

from dataclasses import dataclass

from issuepilot.shared_kernel.events import DomainEvent


@dataclass(frozen=True, slots=True, kw_only=True)
class FeedbackRecorded(DomainEvent):
    feedback_id: str
    run_id: str
    kind: str
