"""Run an investigation (milestone-0 pipeline).

This is the simplest honest pipeline through the real ports: retrieve
candidates, ask the reasoning model, keep only claims whose citations verify
against the snapshot, and build a report that satisfies the domain invariant.
The v0.1 ReAct strategy replaces the middle of this pipeline; the boundary —
verified evidence in, invariant-checked report out — stays.
"""

from __future__ import annotations

from issuepilot.investigation.application.dto import FindingDTO, ReportDTO
from issuepilot.investigation.application.ports import (
    CitationVerifierPort,
    ModelRequest,
    ReasoningModelPort,
    RunStorePort,
    SearchPort,
)
from issuepilot.investigation.domain.events import InvestigationCompleted, InvestigationStarted
from issuepilot.investigation.domain.evidence import EvidenceReference
from issuepilot.investigation.domain.report import (
    Finding,
    InvestigationReport,
    ReportCompleteness,
)
from issuepilot.investigation.domain.values import Confidence, IssueStatement
from issuepilot.shared_kernel.cancellation import NEVER_CANCELLED, CancellationToken
from issuepilot.shared_kernel.clock import Clock
from issuepilot.shared_kernel.errors import EvidenceRequirementError
from issuepilot.shared_kernel.events import EventBus
from issuepilot.shared_kernel.ids import EventId, IdGenerator, ReportId, RunId


class RunInvestigation:
    def __init__(
        self,
        *,
        model: ReasoningModelPort,
        search: SearchPort,
        verifier: CitationVerifierPort,
        store: RunStorePort,
        ids: IdGenerator,
        clock: Clock,
        bus: EventBus,
        candidate_limit: int = 8,
    ) -> None:
        self._model = model
        self._search = search
        self._verifier = verifier
        self._store = store
        self._ids = ids
        self._clock = clock
        self._bus = bus
        self._candidate_limit = candidate_limit

    def execute(
        self,
        issue: IssueStatement,
        commit_sha: str,
        *,
        cancellation: CancellationToken = NEVER_CANCELLED,
    ) -> ReportDTO:
        run_id = RunId(self._ids.new_id())
        self._bus.publish(
            InvestigationStarted(
                event_id=EventId(self._ids.new_id()),
                occurred_at=self._clock.now(),
                aggregate_id=run_id,
                run_id=run_id,
                snapshot_sha=commit_sha,
            )
        )

        cancellation.raise_if_cancelled()
        candidates = self._search.search(issue.summary_line, limit=self._candidate_limit)

        verified = tuple(
            EvidenceReference(
                path=c.path,
                start_line=c.start_line,
                end_line=c.end_line,
                commit_sha=c.commit_sha,
            )
            for c in candidates
            if c.commit_sha == commit_sha
            and self._verifier.verify(c.path, c.start_line, c.end_line, c.commit_sha)
        )
        if not verified:
            raise EvidenceRequirementError(
                "no retrieved evidence could be verified against the snapshot",
                remediation="re-index the repository or broaden the issue statement",
            )

        cancellation.raise_if_cancelled()
        answer = self._model.complete(ModelRequest(prompt=self._build_prompt(issue, verified)))

        report = InvestigationReport(
            report_id=ReportId(self._ids.new_id()),
            run_id=run_id,
            commit_sha=commit_sha,
            issue_summary=issue.summary_line,
            findings=(
                Finding(
                    claim=answer.strip(),
                    confidence=Confidence(0.5),
                    evidence=verified,
                ),
            ),
            completeness=ReportCompleteness.COMPLETE,
        )
        dto = to_dto(report)
        self._store.save_report(dto)
        self._bus.publish(
            InvestigationCompleted(
                event_id=EventId(self._ids.new_id()),
                occurred_at=self._clock.now(),
                aggregate_id=run_id,
                run_id=run_id,
                report_id=report.report_id,
                finding_count=len(report.findings),
            )
        )
        return dto

    @staticmethod
    def _build_prompt(issue: IssueStatement, evidence: tuple[EvidenceReference, ...]) -> str:
        cited = "\n".join(f"- {ref.cite()}" for ref in evidence)
        return (
            f"Issue under investigation:\n{issue.text}\n\nVerified evidence locations:\n{cited}\n"
        )


def to_dto(report: InvestigationReport) -> ReportDTO:
    return ReportDTO(
        report_id=report.report_id,
        run_id=report.run_id,
        commit_sha=report.commit_sha,
        issue_summary=report.issue_summary,
        completeness=report.completeness.value,
        findings=tuple(
            FindingDTO(
                claim=f.claim,
                confidence=f.confidence.value,
                citations=tuple(ref.cite() for ref in f.evidence),
                speculative=f.speculative,
            )
            for f in report.findings
        ),
        missing_information=report.missing_information,
    )
