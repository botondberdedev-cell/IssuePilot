"""Wires the feedback context."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence

from issuepilot.feedback.application.dto import DraftCase
from issuepilot.feedback.application.public import FeedbackFacade
from issuepilot.feedback.application.use_cases.export_candidates import export_candidates
from issuepilot.feedback.domain.feedback import FeedbackKind
from issuepilot.feedback.infrastructure.feedback_repo import SqliteFeedbackStore
from issuepilot.investigation.application.public import InvestigationFacade
from issuepilot.shared_kernel.clock import Clock
from issuepilot.shared_kernel.events import EventBus
from issuepilot.shared_kernel.ids import IdGenerator, RunId


def build_feedback_facade(
    *,
    connection: sqlite3.Connection,
    ids: IdGenerator,
    clock: Clock,
    bus: EventBus,
) -> FeedbackFacade:
    store = SqliteFeedbackStore(connection, clock.now())
    return FeedbackFacade(store, ids, clock, bus)


class FeedbackServiceAdapter:
    """Presents the feedback facade in the primitives the CLI speaks.

    Export needs the original issue text, which lives in the investigation
    context — so this adapter is where the two meet, not either context.
    """

    def __init__(
        self,
        facade: FeedbackFacade,
        store: SqliteFeedbackStore,
        investigation: InvestigationFacade,
    ) -> None:
        self._facade = facade
        self._store = store
        self._investigation = investigation

    def accept(self, run_id: str) -> None:
        self._facade.record(RunId(run_id), FeedbackKind.ACCEPT)

    def reject(self, run_id: str, note: str = "") -> None:
        self._facade.record(RunId(run_id), FeedbackKind.REJECT, note)

    def correct(self, run_id: str, note: str) -> None:
        self._facade.record(RunId(run_id), FeedbackKind.CORRECT, note)

    def export_candidates(self) -> Sequence[DraftCase]:
        entries = self._store.list_recent()
        issues: dict[str, str] = {
            str(entry.run_id): report.issue_summary
            for entry in entries
            if (report := self._investigation.get_report(entry.run_id)) is not None
        }
        return export_candidates(entries, issues)
