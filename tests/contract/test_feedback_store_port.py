"""Contract suite for FeedbackStorePort (SQLite adapter joins in v0.1)."""

from __future__ import annotations

import pytest

from issuepilot.feedback.application.ports import FeedbackStorePort
from issuepilot.feedback.domain.feedback import FeedbackKind, UserFeedback
from issuepilot.shared_kernel.ids import FeedbackId, RunId, new_ulid
from tests.support.fakes.feedback_store import InMemoryFeedbackStore


@pytest.fixture(params=["fake"])
def store(request: pytest.FixtureRequest) -> FeedbackStorePort:
    return InMemoryFeedbackStore()


def _feedback(run_id: RunId, kind: FeedbackKind = FeedbackKind.ACCEPT) -> UserFeedback:
    return UserFeedback(
        feedback_id=FeedbackId(new_ulid()),
        run_id=run_id,
        kind=kind,
        note="wrong file cited" if kind is FeedbackKind.CORRECT else "",
    )


def test_add_then_list_roundtrip(store: FeedbackStorePort) -> None:
    run_id = RunId(new_ulid())
    feedback = _feedback(run_id)
    store.add(feedback)
    assert list(store.list_for_run(run_id)) == [feedback]


def test_listing_filters_by_run(store: FeedbackStorePort) -> None:
    mine, other = RunId(new_ulid()), RunId(new_ulid())
    store.add(_feedback(mine))
    store.add(_feedback(other, FeedbackKind.REJECT))
    assert all(f.run_id == mine for f in store.list_for_run(mine))
    assert len(list(store.list_for_run(mine))) == 1
