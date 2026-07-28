"""Contract suite for the event bus: the fake and the real adapter must agree.

The fixture yields ``(bus, published_ids)`` where ``published_ids`` is a probe
returning the ids of all events observable after publishing — from memory for
the fake, from the outbox table for the SQLite bus.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from issuepilot.adapters.eventbus import SqliteOutboxEventBus
from issuepilot.adapters.sqlite.connection import connect
from issuepilot.adapters.sqlite.migrator import migrate
from issuepilot.shared_kernel.events import DomainEvent
from issuepilot.shared_kernel.ids import EventId, new_ulid
from tests.support.fakes.eventbus import RecordingEventBus


@dataclass(frozen=True, slots=True, kw_only=True)
class _SomethingHappened(DomainEvent):
    detail: str


@dataclass(frozen=True, slots=True, kw_only=True)
class _OtherThingHappened(DomainEvent):
    pass


class _Recorder:
    def __init__(self) -> None:
        self.handled: list[DomainEvent] = []

    def handle(self, event: DomainEvent) -> None:
        self.handled.append(event)


type BusAndProbe = tuple[RecordingEventBus | SqliteOutboxEventBus, Callable[[], list[str]]]


@pytest.fixture(params=["fake", "sqlite"])
def bus_and_probe(request: pytest.FixtureRequest) -> BusAndProbe:
    if request.param == "fake":
        fake = RecordingEventBus()
        return fake, lambda: [e.event_id for e in fake.published]
    conn = connect(":memory:")
    migrate(conn)
    real = SqliteOutboxEventBus(conn)
    return real, lambda: [
        str(row["event_id"]) for row in conn.execute("SELECT event_id FROM outbox_events")
    ]


def _event(detail: str = "x") -> _SomethingHappened:
    return _SomethingHappened(
        event_id=EventId(new_ulid()),
        occurred_at=datetime(2026, 7, 28, tzinfo=UTC),
        aggregate_id="agg-1",
        detail=detail,
    )


def test_published_events_are_observable(bus_and_probe: BusAndProbe) -> None:
    bus, probe = bus_and_probe
    event = _event()
    bus.publish(event)
    assert probe() == [event.event_id]


def test_subscriber_receives_matching_events_only(bus_and_probe: BusAndProbe) -> None:
    bus, _ = bus_and_probe
    recorder = _Recorder()
    bus.subscribe(_SomethingHappened, recorder)
    matching = _event()
    other = _OtherThingHappened(
        event_id=EventId(new_ulid()),
        occurred_at=datetime(2026, 7, 28, tzinfo=UTC),
        aggregate_id="agg-2",
    )
    bus.publish(matching)
    bus.publish(other)
    assert recorder.handled == [matching]


def test_subscribers_run_in_registration_order(bus_and_probe: BusAndProbe) -> None:
    bus, _ = bus_and_probe
    order: list[str] = []

    class _Named:
        def __init__(self, name: str) -> None:
            self._name = name

        def handle(self, event: DomainEvent) -> None:
            order.append(self._name)

    bus.subscribe(_SomethingHappened, _Named("first"))
    bus.subscribe(_SomethingHappened, _Named("second"))
    bus.publish(_event())
    assert order == ["first", "second"]
