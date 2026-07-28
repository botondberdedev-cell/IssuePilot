"""User feedback on investigation runs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, unique

from issuepilot.shared_kernel.ids import FeedbackId, RunId


@unique
class FeedbackKind(Enum):
    ACCEPT = "accept"
    REJECT = "reject"
    CORRECT = "correct"


@dataclass(frozen=True, slots=True)
class UserFeedback:
    feedback_id: FeedbackId
    run_id: RunId
    kind: FeedbackKind
    note: str = ""

    def __post_init__(self) -> None:
        if self.kind is FeedbackKind.CORRECT and not self.note.strip():
            raise ValueError("a correction requires a note describing what was wrong")
