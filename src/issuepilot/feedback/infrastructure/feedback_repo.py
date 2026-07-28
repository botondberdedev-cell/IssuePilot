"""SQLite-backed user feedback."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from datetime import datetime

from issuepilot.feedback.domain.feedback import FeedbackKind, UserFeedback
from issuepilot.shared_kernel.ids import FeedbackId, RunId


class SqliteFeedbackStore:
    def __init__(self, connection: sqlite3.Connection, recorded_at: datetime) -> None:
        self._connection = connection
        self._recorded_at = recorded_at

    def add(self, feedback: UserFeedback) -> None:
        self._connection.execute(
            "INSERT OR REPLACE INTO fbk_feedback"
            " (feedback_id, run_id, kind, note, recorded_at) VALUES (?, ?, ?, ?, ?)",
            (
                feedback.feedback_id,
                feedback.run_id,
                feedback.kind.value,
                feedback.note,
                self._recorded_at.isoformat(),
            ),
        )

    def list_for_run(self, run_id: RunId) -> Sequence[UserFeedback]:
        rows = self._connection.execute(
            "SELECT * FROM fbk_feedback WHERE run_id = ? ORDER BY feedback_id", (run_id,)
        ).fetchall()
        return tuple(_to_feedback(row) for row in rows)

    def list_recent(self, limit: int = 50) -> Sequence[UserFeedback]:
        rows = self._connection.execute(
            "SELECT * FROM fbk_feedback ORDER BY feedback_id DESC LIMIT ?", (limit,)
        ).fetchall()
        return tuple(_to_feedback(row) for row in rows)


def _to_feedback(row: sqlite3.Row) -> UserFeedback:
    return UserFeedback(
        feedback_id=FeedbackId(row["feedback_id"]),
        run_id=RunId(row["run_id"]),
        kind=FeedbackKind(row["kind"]),
        note=row["note"],
    )
