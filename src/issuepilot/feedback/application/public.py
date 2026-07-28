"""The feedback context's public facade."""

from __future__ import annotations

from issuepilot.feedback.application.ports import FeedbackStorePort
from issuepilot.feedback.domain.events import FeedbackRecorded
from issuepilot.feedback.domain.feedback import FeedbackKind, UserFeedback
from issuepilot.shared_kernel.clock import Clock
from issuepilot.shared_kernel.events import EventBus
from issuepilot.shared_kernel.ids import EventId, FeedbackId, IdGenerator, RunId


class FeedbackFacade:
    def __init__(
        self,
        store: FeedbackStorePort,
        ids: IdGenerator,
        clock: Clock,
        bus: EventBus,
    ) -> None:
        self._store = store
        self._ids = ids
        self._clock = clock
        self._bus = bus

    def record(self, run_id: RunId, kind: FeedbackKind, note: str = "") -> UserFeedback:
        feedback = UserFeedback(
            feedback_id=FeedbackId(self._ids.new_id()),
            run_id=run_id,
            kind=kind,
            note=note,
        )
        self._store.add(feedback)
        self._bus.publish(
            FeedbackRecorded(
                event_id=EventId(self._ids.new_id()),
                occurred_at=self._clock.now(),
                aggregate_id=feedback.feedback_id,
                feedback_id=feedback.feedback_id,
                run_id=run_id,
                kind=kind.value,
            )
        )
        return feedback
