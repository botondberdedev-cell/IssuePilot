"""Every context's domain events must be constructible, frozen, and typed.

Catches dataclass-inheritance mistakes (missing kw_only, slots clashes)
without waiting for the feature that first publishes each event.
"""

from __future__ import annotations

import dataclasses
import importlib
import inspect
from datetime import UTC, datetime
from typing import Any

import pytest

from issuepilot.shared_kernel.events import DomainEvent

EVENT_MODULES = [
    "issuepilot.repository.domain.events",
    "issuepilot.knowledge.domain.events",
    "issuepilot.investigation.domain.events",
    "issuepilot.evaluation.domain.events",
    "issuepilot.governance.domain.events",
    "issuepilot.feedback.domain.events",
]


def _all_event_classes() -> list[type[DomainEvent]]:
    classes: list[type[DomainEvent]] = []
    for module_name in EVENT_MODULES:
        module = importlib.import_module(module_name)
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, DomainEvent) and obj.__module__ == module_name:
                classes.append(obj)
    return classes


def _dummy_for(field: dataclasses.Field[Any]) -> object:
    if field.type in ("int", int):
        return 1
    if field.type in ("datetime", datetime):
        return datetime(2026, 7, 28, tzinfo=UTC)
    return "x"


def _construct(event_class: type[DomainEvent]) -> DomainEvent:
    kwargs = {f.name: _dummy_for(f) for f in dataclasses.fields(event_class)}
    kwargs["occurred_at"] = datetime(2026, 7, 28, tzinfo=UTC)
    return event_class(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize("event_class", _all_event_classes(), ids=lambda c: c.__name__)
def test_event_is_constructible_frozen_and_named(event_class: type[DomainEvent]) -> None:
    event = _construct(event_class)
    assert event.event_type == event_class.__name__
    assert event.occurred_at.tzinfo is not None
    first_field = dataclasses.fields(event_class)[0].name
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(event, first_field, "mutated")


def test_smoke_covers_a_reasonable_event_population() -> None:
    assert len(_all_event_classes()) >= 10
