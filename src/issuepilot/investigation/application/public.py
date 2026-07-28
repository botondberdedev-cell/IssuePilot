"""The investigation context's public facade."""

from __future__ import annotations

from issuepilot.investigation.application.dto import ReportDTO
from issuepilot.investigation.application.use_cases.run_investigation import RunInvestigation
from issuepilot.investigation.domain.values import IssueStatement
from issuepilot.shared_kernel.cancellation import NEVER_CANCELLED, CancellationToken


class InvestigationFacade:
    def __init__(self, run_investigation: RunInvestigation) -> None:
        self._run_investigation = run_investigation

    def investigate(
        self,
        issue_text: str,
        commit_sha: str,
        *,
        cancellation: CancellationToken = NEVER_CANCELLED,
    ) -> ReportDTO:
        issue = IssueStatement(issue_text)
        return self._run_investigation.execute(issue, commit_sha, cancellation=cancellation)
