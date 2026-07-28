from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from issuepilot.shared_kernel.events import DomainEvent
from issuepilot.shared_kernel.ids import EventId, new_ulid


@dataclass(frozen=True, slots=True, kw_only=True)
class _ThingHappened(DomainEvent):
    detail: str


def _event(detail: str = "x") -> _ThingHappened:
    return _ThingHappened(
        event_id=EventId(new_ulid()),
        occurred_at=datetime(2026, 7, 28, tzinfo=UTC),
        aggregate_id="agg-1",
        detail=detail,
    )


def test_event_type_is_class_name() -> None:
    assert _event().event_type == "_ThingHappened"


def test_events_are_immutable() -> None:
    event = _event()
    with pytest.raises(dataclasses.FrozenInstanceError):
        event.detail = "changed"  # type: ignore[misc]


def test_naive_timestamp_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _ThingHappened(
            event_id=EventId(new_ulid()),
            occurred_at=datetime(2026, 7, 28),
            aggregate_id="agg-1",
            detail="x",
        )
