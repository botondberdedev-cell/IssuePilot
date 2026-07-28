"""The investigation context's public facade."""

from __future__ import annotations

from collections.abc import Sequence

from issuepilot.investigation.application.dto import ReportDTO
from issuepilot.investigation.application.ports import RunStorePort
from issuepilot.investigation.application.use_cases.run_investigation import (
    InvestigateCommand,
    RunInvestigation,
)
from issuepilot.investigation.domain.values import IssueStatement
from issuepilot.shared_kernel.cancellation import NEVER_CANCELLED, CancellationToken
from issuepilot.shared_kernel.ids import RunId


class InvestigationFacade:
    def __init__(self, run_investigation: RunInvestigation, store: RunStorePort) -> None:
        self._run_investigation = run_investigation
        self._store = store

    def investigate(
        self,
        issue_text: str,
        commit_sha: str,
        *,
        max_steps: int = 12,
        cancellation: CancellationToken = NEVER_CANCELLED,
        on_step: object = None,
    ) -> ReportDTO:
        command = InvestigateCommand(
            issue=IssueStatement(issue_text),
            commit_sha=commit_sha,
            max_steps=max_steps,
        )
        return self._run_investigation.execute(command, cancellation=cancellation, on_step=on_step)

    def get_report(self, run_id: str) -> ReportDTO | None:
        return self._store.load_report(RunId(run_id))

    def recent_reports(self, limit: int = 20) -> Sequence[ReportDTO]:
        return self._store.list_recent(limit)
