from __future__ import annotations

from collections import defaultdict

from issuepilot.shared_kernel.events import DomainEvent, EventSubscriber


class RecordingEventBus:
    """In-memory event bus: records everything, dispatches to exact-type subscribers."""

    def __init__(self) -> None:
        self.published: list[DomainEvent] = []
        self._subscribers: defaultdict[type[DomainEvent], list[EventSubscriber]] = defaultdict(list)

    def subscribe(self, event_type: type[DomainEvent], subscriber: EventSubscriber) -> None:
        self._subscribers[event_type].append(subscriber)

    def publish(self, event: DomainEvent) -> None:
        self.published.append(event)
        for subscriber in self._subscribers[type(event)]:
            subscriber.handle(event)
