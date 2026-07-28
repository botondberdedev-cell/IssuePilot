"""The investigation report and its central invariant.

A ``Finding`` is either evidence-backed (at least one ``EvidenceReference``)
or explicitly marked speculation — there is no third state, and the
constructor makes an unevidenced factual claim unrepresentable. Every
evidence reference must belong to the report's snapshot commit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, unique

from issuepilot.investigation.domain.evidence import EvidenceReference
from issuepilot.investigation.domain.values import Confidence
from issuepilot.shared_kernel.ids import ReportId, RunId


@unique
class ReportCompleteness(Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    """Budget exhausted or cancelled: the report says so, it never pretends."""


@dataclass(frozen=True, slots=True)
class Finding:
    claim: str
    confidence: Confidence
    evidence: tuple[EvidenceReference, ...]
    speculative: bool = False
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.claim.strip():
            raise ValueError("a finding needs a claim")
        if not self.evidence and not self.speculative:
            raise ValueError("a factual finding requires evidence; mark it speculative or drop it")


@dataclass(frozen=True, slots=True)
class InvestigationReport:
    report_id: ReportId
    run_id: RunId
    commit_sha: str
    issue_summary: str
    findings: tuple[Finding, ...]
    completeness: ReportCompleteness
    missing_information: tuple[str, ...] = field(default=())

    def __post_init__(self) -> None:
        # A report with no findings is valid *only* when it explains what it
        # could not establish. Saying "the repository does not answer this" is
        # a correct outcome; saying nothing at all is not.
        if not self.findings and not self.missing_information:
            raise ValueError("a report must contain findings or explain what is missing")
        for finding in self.findings:
            for reference in finding.evidence:
                if reference.commit_sha != self.commit_sha:
                    raise ValueError(
                        f"evidence {reference.cite()} does not belong to report snapshot "
                        f"{self.commit_sha[:12]}"
                    )

    @property
    def evidence_backed_findings(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if not f.speculative)
