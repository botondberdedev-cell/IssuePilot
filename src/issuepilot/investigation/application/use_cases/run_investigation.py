"""Run an investigation and synthesize a cited report.

The boundary this use case defends: *verified evidence in, invariant-checked
report out*. The model proposes claims and points at evidence by index; this
code decides what may be cited. A claim whose evidence does not verify
against the snapshot is demoted to speculation rather than dropped silently,
so the report shows what the model believed and what could not be confirmed.
"""

from __future__ import annotations

from dataclasses import dataclass

from issuepilot.investigation.application.dto import (
    EvidenceCandidateDTO,
    FindingDTO,
    ReportDTO,
)
from issuepilot.investigation.application.ports import (
    CitationVerifierPort,
    PromptPort,
    ReasoningModelPort,
    RunStorePort,
    StructuredRequest,
)
from issuepilot.investigation.application.strategies.react import (
    SYSTEM_PROMPT,
    InvestigationOutcome,
    ReActStrategy,
)
from issuepilot.investigation.domain.budget import StepBudget
from issuepilot.investigation.domain.events import (
    InvestigationCompleted,
    InvestigationStarted,
)
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

_MAX_EVIDENCE_IN_PROMPT = 12


@dataclass(frozen=True, slots=True)
class InvestigateCommand:
    issue: IssueStatement
    commit_sha: str
    max_steps: int = 12


class RunInvestigation:
    def __init__(
        self,
        *,
        strategy_factory: object,
        model: ReasoningModelPort,
        prompts: PromptPort,
        verifier: CitationVerifierPort,
        store: RunStorePort,
        ids: IdGenerator,
        clock: Clock,
        bus: EventBus,
    ) -> None:
        self._strategy_factory = strategy_factory
        self._model = model
        self._prompts = prompts
        self._verifier = verifier
        self._store = store
        self._ids = ids
        self._clock = clock
        self._bus = bus

    def execute(
        self,
        command: InvestigateCommand,
        *,
        cancellation: CancellationToken = NEVER_CANCELLED,
        on_step: object = None,
    ) -> ReportDTO:
        run_id = RunId(self._ids.new_id())
        self._publish_started(run_id, command.commit_sha)

        strategy = self._build_strategy(command.commit_sha)
        outcome = strategy.investigate(
            command.issue,
            StepBudget(limit=command.max_steps),
            cancellation=cancellation,
            on_step=on_step,
        )

        verified = self._verify(outcome.evidence, command.commit_sha)
        if not verified:
            raise EvidenceRequirementError(
                "the investigation ended without any verifiable evidence",
                remediation=("re-index the repository, raise --max-steps, or restate the issue"),
            )

        report = self._synthesize(run_id, command, outcome, verified)
        dto = to_dto(report)
        self._store.save_report(dto)
        self._publish_completed(run_id, report)
        return dto

    def _build_strategy(self, commit_sha: str) -> ReActStrategy:
        factory = self._strategy_factory
        if not callable(factory):  # pragma: no cover - wiring guarantees callable
            raise TypeError("strategy_factory must be callable")
        built: ReActStrategy = factory(commit_sha)
        return built

    def _verify(
        self, candidates: tuple[EvidenceCandidateDTO, ...], commit_sha: str
    ) -> list[tuple[EvidenceCandidateDTO, EvidenceReference]]:
        """Keep only evidence that still resolves in this exact snapshot."""
        verified: list[tuple[EvidenceCandidateDTO, EvidenceReference]] = []
        for candidate in candidates:
            if candidate.commit_sha != commit_sha:
                continue
            if not self._verifier.verify(
                candidate.path, candidate.start_line, candidate.end_line, commit_sha
            ):
                continue
            verified.append(
                (
                    candidate,
                    EvidenceReference(
                        path=candidate.path,
                        start_line=candidate.start_line,
                        end_line=candidate.end_line,
                        commit_sha=commit_sha,
                    ),
                )
            )
        return verified

    def _synthesize(
        self,
        run_id: RunId,
        command: InvestigateCommand,
        outcome: InvestigationOutcome,
        verified: list[tuple[EvidenceCandidateDTO, EvidenceReference]],
    ) -> InvestigationReport:
        shown = verified[:_MAX_EVIDENCE_IN_PROMPT]
        rendered = self._prompts.render(
            "report@v1",
            issue=command.issue.text,
            evidence=[
                {
                    "path": candidate.path,
                    "start_line": candidate.start_line,
                    "end_line": candidate.end_line,
                    "snippet": candidate.snippet,
                }
                for candidate, _ in shown
            ],
        )
        reply = self._model.generate(
            StructuredRequest(
                prompt_name=rendered.name,
                system=SYSTEM_PROMPT,
                user=rendered.text,
                schema=rendered.schema,
            )
        )

        references = [reference for _, reference in shown]
        findings = _build_findings(reply.data, references)
        if not findings:
            # The model produced nothing citable. Rather than fail, report the
            # evidence that was gathered and mark the gap honestly.
            findings = (
                Finding(
                    claim="Relevant code was located but no conclusion could be drawn.",
                    confidence=Confidence(0.1),
                    evidence=tuple(references[:3]),
                ),
            )

        missing = _string_list(reply.data.get("missing_information"))
        if outcome.budget_exhausted:
            missing = (*missing, "The step budget ran out before the agent finished.")

        return InvestigationReport(
            report_id=ReportId(self._ids.new_id()),
            run_id=run_id,
            commit_sha=command.commit_sha,
            issue_summary=str(reply.data.get("summary") or command.issue.summary_line),
            findings=findings,
            completeness=(
                ReportCompleteness.PARTIAL
                if outcome.budget_exhausted
                else ReportCompleteness.COMPLETE
            ),
            missing_information=missing,
        )

    def _publish_started(self, run_id: RunId, commit_sha: str) -> None:
        self._bus.publish(
            InvestigationStarted(
                event_id=EventId(self._ids.new_id()),
                occurred_at=self._clock.now(),
                aggregate_id=run_id,
                run_id=run_id,
                snapshot_sha=commit_sha,
            )
        )

    def _publish_completed(self, run_id: RunId, report: InvestigationReport) -> None:
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


def _build_findings(data: object, references: list[EvidenceReference]) -> tuple[Finding, ...]:
    """Map model findings onto verified evidence.

    An index the model invented refers to nothing we verified, so the claim
    keeps only the references that exist. A claim left with none becomes
    explicit speculation — never a bare factual assertion.
    """
    if not isinstance(data, dict):  # pragma: no cover - schema guarantees a dict
        return ()
    raw_findings = data.get("findings")
    if not isinstance(raw_findings, list):
        return ()

    findings: list[Finding] = []
    for entry in raw_findings:
        if not isinstance(entry, dict):
            continue
        claim = str(entry.get("claim", "")).strip()
        if not claim:
            continue
        cited = [
            references[index]
            for index in _int_list(entry.get("evidence_indices"))
            if 0 <= index < len(references)
        ]
        findings.append(
            Finding(
                claim=claim,
                confidence=Confidence(_clamp(entry.get("confidence"))),
                evidence=tuple(cited),
                speculative=not cited,
            )
        )
    return tuple(findings)


def _clamp(value: object) -> float:
    if not isinstance(value, int | float | str) or isinstance(value, bool):
        return 0.5
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.5
    return min(1.0, max(0.0, number))


def _int_list(value: object) -> list[int]:
    if not isinstance(value, list):
        return []
    result: list[int] = []
    for item in value:
        if isinstance(item, bool):
            continue
        if isinstance(item, int):
            result.append(item)
        elif isinstance(item, str | float):
            try:
                result.append(int(item))
            except (TypeError, ValueError):
                continue
    return result


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


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
