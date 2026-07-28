"""In-process event bus: synchronous dispatch plus SQLite outbox write.

The outbox row is inserted first (joining the caller's open transaction when
there is one), then subscribers run synchronously in registration order.
Subscribers are matched on the exact event class.
"""

from __future__ import annotations

import dataclasses
import json
import sqlite3
from collections import defaultdict

from issuepilot.shared_kernel.events import DomainEvent, EventSubscriber


class SqliteOutboxEventBus:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._subscribers: defaultdict[type[DomainEvent], list[EventSubscriber]] = defaultdict(list)

    def subscribe(self, event_type: type[DomainEvent], subscriber: EventSubscriber) -> None:
        self._subscribers[event_type].append(subscriber)

    def publish(self, event: DomainEvent) -> None:
        payload = json.dumps(dataclasses.asdict(event), default=str, sort_keys=True)
        self._conn.execute(
            "INSERT INTO outbox_events (event_id, event_type, aggregate_id, occurred_at, payload)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                event.event_id,
                event.event_type,
                event.aggregate_id,
                event.occurred_at.isoformat(),
                payload,
            ),
        )
        for subscriber in self._subscribers[type(event)]:
            subscriber.handle(event)
