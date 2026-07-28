"""``issuepilot investigate`` end to end: output contract, formats, exit codes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from issuepilot.adapters.cli.app import run
from issuepilot.adapters.cli.services import CheckResult, CliServices
from issuepilot.shared_kernel.cancellation import CancellationToken
from issuepilot.shared_kernel.errors import EvidenceRequirementError, OperationInterruptedError
from tests.support.fakes.services import (
    DEFAULT_SHA,
    StubEvaluationService,
    StubFeedbackService,
    StubInvestigationService,
    StubKnowledgeService,
    StubRepositoryService,
)

pytestmark = pytest.mark.e2e


def services(investigation: StubInvestigationService | None = None) -> CliServices:
    return CliServices(
        version="0.0.0-test",
        cancellation=CancellationToken(),
        environment_checks=[lambda: CheckResult("git", True, "ok")],
        config_dump={},
        repository=StubRepositoryService(),
        knowledge=StubKnowledgeService(),
        investigation=investigation or StubInvestigationService(),
        evaluation=StubEvaluationService(),
        feedback=StubFeedbackService(),
    )


REPO = "https://example.com/a/b.git"


class TestIssueInput:
    def test_issue_flag_reaches_the_service(self) -> None:
        stub = StubInvestigationService()
        assert run(services(stub), ["investigate", REPO, "--issue", "refunds stuck"]) == 0
        assert stub.issues == ["refunds stuck"]

    def test_issue_file_is_read(self, tmp_path: Path) -> None:
        issue_file = tmp_path / "issue.md"
        issue_file.write_text("# Bug\n\nRefunds stay pending.\n", encoding="utf-8")
        stub = StubInvestigationService()
        code = run(services(stub), ["investigate", REPO, "--issue-file", str(issue_file)])
        assert code == 0
        assert "Refunds stay pending." in stub.issues[0]

    def test_missing_issue_is_a_usage_error(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert run(services(), ["investigate", REPO]) == 2
        assert "no issue supplied" in capsys.readouterr().err

    def test_both_issue_sources_is_a_usage_error(self) -> None:
        assert run(services(), ["investigate", REPO, "--issue", "x", "--issue-file", "y"]) == 2

    def test_missing_issue_file_is_a_usage_error(self) -> None:
        assert run(services(), ["investigate", REPO, "--issue-file", "/nope.md"]) == 2


class TestOutput:
    def test_terminal_report_shows_claim_commit_and_citation(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        run(services(), ["investigate", REPO, "--issue", "refunds"])
        out = capsys.readouterr().out
        assert "returns before the transition commits" in out
        assert DEFAULT_SHA in out
        assert "src/refunds/webhook.py:84-121" in out

    def test_progress_goes_to_stderr_only(self, capsys: pytest.CaptureFixture[str]) -> None:
        run(services(), ["investigate", REPO, "--issue", "refunds"])
        captured = capsys.readouterr()
        assert "investigating" in captured.err
        assert "investigating" not in captured.out

    def test_json_is_pure_and_versioned(self, capsys: pytest.CaptureFixture[str]) -> None:
        run(services(), ["investigate", REPO, "--issue", "refunds", "--format", "json"])
        document = json.loads(capsys.readouterr().out)
        assert document["format_version"] == 1
        assert document["commit_sha"] == DEFAULT_SHA
        assert document["findings"][0]["citations"]

    def test_markdown_renders_headings_and_evidence(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        run(services(), ["investigate", REPO, "--issue", "refunds", "--format", "markdown"])
        out = capsys.readouterr().out
        assert out.startswith("# ")
        assert "Evidence:" in out
        assert DEFAULT_SHA in out

    def test_output_file_is_written(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        destination = tmp_path / "report.md"
        run(
            services(),
            [
                "investigate",
                REPO,
                "--issue",
                "refunds",
                "--format",
                "markdown",
                "--output",
                str(destination),
            ],
        )
        assert destination.is_file()
        assert "Evidence:" in destination.read_text(encoding="utf-8")


class TestExitCodes:
    def test_unmet_evidence_requirement_exits_five(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        stub = StubInvestigationService(
            error=EvidenceRequirementError(
                "no verifiable evidence", remediation="re-index the repository"
            )
        )
        assert run(services(stub), ["investigate", REPO, "--issue", "refunds"]) == 5
        captured = capsys.readouterr()
        assert "no verifiable evidence" in captured.err
        assert captured.out == ""

    def test_cancellation_exits_eight(self) -> None:
        stub = StubInvestigationService(error=OperationInterruptedError("cancelled"))
        assert run(services(stub), ["investigate", REPO, "--issue", "refunds"]) == 8


class TestRunsListing:
    def test_runs_lists_previous_investigations(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert run(services(), ["runs"]) == 0
        assert DEFAULT_SHA[:12] in capsys.readouterr().out

    def test_runs_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert run(services(), ["runs", "--format", "json"]) == 0
        assert json.loads(capsys.readouterr().out)[0]["commit_sha"] == DEFAULT_SHA
