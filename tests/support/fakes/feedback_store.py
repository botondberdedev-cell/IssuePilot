from __future__ import annotations

from collections.abc import Sequence

from issuepilot.feedback.domain.feedback import UserFeedback
from issuepilot.shared_kernel.ids import RunId


class InMemoryFeedbackStore:
    def __init__(self) -> None:
        self._items: list[UserFeedback] = []

    def add(self, feedback: UserFeedback) -> None:
        self._items.append(feedback)

    def list_for_run(self, run_id: RunId) -> Sequence[UserFeedback]:
        return tuple(f for f in self._items if f.run_id == run_id)
