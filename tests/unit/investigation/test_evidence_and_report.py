from __future__ import annotations

import pytest

from issuepilot.investigation.domain.evidence import EvidenceReference
from issuepilot.investigation.domain.report import (
    Finding,
    InvestigationReport,
    ReportCompleteness,
)
from issuepilot.investigation.domain.values import Confidence
from issuepilot.shared_kernel.ids import ReportId, RunId, new_ulid

SHA = "a" * 40
OTHER_SHA = "b" * 40


def evidence(path: str = "src/app.py", sha: str = SHA) -> EvidenceReference:
    return EvidenceReference(path=path, start_line=10, end_line=20, commit_sha=sha)


class TestEvidenceReference:
    def test_cite_renders_path_lines_and_short_sha(self) -> None:
        assert evidence().cite() == f"src/app.py:10-20 @ {'a' * 12}"

    @pytest.mark.parametrize("bad_path", ["", "/abs", "~/home", "a/../b", "x\x00y"])
    def test_rejects_unsafe_paths(self, bad_path: str) -> None:
        with pytest.raises(ValueError, match="path"):
            EvidenceReference(path=bad_path, start_line=1, end_line=1, commit_sha=SHA)

    def test_rejects_short_sha(self) -> None:
        with pytest.raises(ValueError, match="full commit sha"):
            EvidenceReference(path="a.py", start_line=1, end_line=1, commit_sha="abc123")

    def test_rejects_inverted_range(self) -> None:
        with pytest.raises(ValueError, match="line range"):
            EvidenceReference(path="a.py", start_line=5, end_line=4, commit_sha=SHA)


class TestFindingInvariant:
    def test_factual_finding_requires_evidence(self) -> None:
        with pytest.raises(ValueError, match="requires evidence"):
            Finding(claim="the bug is in the retry path", confidence=Confidence(0.8), evidence=())

    def test_speculation_is_allowed_without_evidence_but_marked(self) -> None:
        finding = Finding(
            claim="this might be a race",
            confidence=Confidence(0.3),
            evidence=(),
            speculative=True,
        )
        assert finding.speculative

    def test_empty_claim_rejected(self) -> None:
        with pytest.raises(ValueError, match="claim"):
            Finding(claim="  ", confidence=Confidence(0.5), evidence=(evidence(),))


class TestReportInvariant:
    def _report(self, findings: tuple[Finding, ...]) -> InvestigationReport:
        return InvestigationReport(
            report_id=ReportId(new_ulid()),
            run_id=RunId(new_ulid()),
            commit_sha=SHA,
            issue_summary="refunds stuck in pending",
            findings=findings,
            completeness=ReportCompleteness.COMPLETE,
        )

    def test_valid_report_builds(self) -> None:
        report = self._report(
            (Finding(claim="cause found", confidence=Confidence(0.7), evidence=(evidence(),)),)
        )
        assert len(report.evidence_backed_findings) == 1

    def test_a_report_saying_nothing_at_all_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="findings or explain what is missing"):
            self._report(())

    def test_a_report_with_no_findings_is_valid_when_it_explains_why(self) -> None:
        """Admitting the repository does not answer the issue is a correct
        outcome, not a malformed report."""
        report = InvestigationReport(
            report_id=ReportId(new_ulid()),
            run_id=RunId(new_ulid()),
            commit_sha=SHA,
            issue_summary="where is the kubernetes operator",
            findings=(),
            completeness=ReportCompleteness.COMPLETE,
            missing_information=("This repository contains no Kubernetes code.",),
        )
        assert report.findings == ()
        assert report.missing_information

    def test_evidence_from_another_snapshot_is_rejected(self) -> None:
        cross = Finding(
            claim="claims another snapshot",
            confidence=Confidence(0.9),
            evidence=(evidence(sha=OTHER_SHA),),
        )
        with pytest.raises(ValueError, match="does not belong to report snapshot"):
            self._report((cross,))

    def test_speculative_findings_are_excluded_from_evidence_backed(self) -> None:
        report = self._report(
            (
                Finding(claim="proven", confidence=Confidence(0.8), evidence=(evidence(),)),
                Finding(claim="guess", confidence=Confidence(0.2), evidence=(), speculative=True),
            )
        )
        assert [f.claim for f in report.evidence_backed_findings] == ["proven"]
