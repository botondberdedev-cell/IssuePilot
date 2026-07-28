"""Ports required by feedback use cases."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from issuepilot.feedback.domain.feedback import UserFeedback
from issuepilot.shared_kernel.ids import RunId


class FeedbackStorePort(Protocol):
    def add(self, feedback: UserFeedback) -> None: ...

    def list_for_run(self, run_id: RunId) -> Sequence[UserFeedback]: ...
