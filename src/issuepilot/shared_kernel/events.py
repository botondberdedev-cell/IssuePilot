"""Domain events and the event bus port.

Events are immutable facts. Contexts publish them through the ``EventBus``
protocol; the concrete bus (in ``adapters/``) dispatches synchronously
in-process and records every event to a SQLite outbox for auditability.
Cross-context knowledge travels through events and IDs — never through
direct imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from issuepilot.shared_kernel.ids import EventId


@dataclass(frozen=True, slots=True, kw_only=True)
class DomainEvent:
    """Base class for all domain events. Subclasses add their own frozen fields."""

    event_id: EventId
    occurred_at: datetime
    aggregate_id: str

    def __post_init__(self) -> None:
        if self.occurred_at.tzinfo is None:
            raise ValueError("DomainEvent.occurred_at must be timezone-aware")

    @property
    def event_type(self) -> str:
        return type(self).__name__


class EventBus(Protocol):
    def publish(self, event: DomainEvent) -> None: ...


class EventSubscriber(Protocol):
    def handle(self, event: DomainEvent) -> None: ...
