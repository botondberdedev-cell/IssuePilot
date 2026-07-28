from __future__ import annotations

from datetime import UTC, datetime

import pytest

from issuepilot.feedback.application.public import FeedbackFacade
from issuepilot.feedback.domain.events import FeedbackRecorded
from issuepilot.feedback.domain.feedback import FeedbackKind, UserFeedback
from issuepilot.shared_kernel.clock import FixedClock
from issuepilot.shared_kernel.ids import FeedbackId, RunId, UlidGenerator, new_ulid
from tests.support.fakes.eventbus import RecordingEventBus
from tests.support.fakes.feedback_store import InMemoryFeedbackStore


def test_correction_requires_a_note() -> None:
    with pytest.raises(ValueError, match="requires a note"):
        UserFeedback(
            feedback_id=FeedbackId(new_ulid()),
            run_id=RunId(new_ulid()),
            kind=FeedbackKind.CORRECT,
        )


def test_facade_stores_and_publishes() -> None:
    store = InMemoryFeedbackStore()
    bus = RecordingEventBus()
    facade = FeedbackFacade(
        store,
        UlidGenerator(),
        FixedClock(datetime(2026, 7, 28, tzinfo=UTC)),
        bus,
    )
    run_id = RunId(new_ulid())
    recorded = facade.record(run_id, FeedbackKind.REJECT)

    assert list(store.list_for_run(run_id)) == [recorded]
    (event,) = bus.published
    assert isinstance(event, FeedbackRecorded)
    assert event.kind == "reject"
