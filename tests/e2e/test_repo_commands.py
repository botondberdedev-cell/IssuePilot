"""``issuepilot repo`` end to end: output contract, formats, exit codes."""

from __future__ import annotations

import json

import pytest

from issuepilot.adapters.cli.app import run
from issuepilot.adapters.cli.services import CheckResult, CliServices
from issuepilot.shared_kernel.cancellation import CancellationToken
from issuepilot.shared_kernel.errors import AcquisitionError, PolicyDeniedError
from tests.support.fakes.services import (
    DEFAULT_SHA,
    StubEvaluationService,
    StubInvestigationService,
    StubKnowledgeService,
    StubRepositoryService,
)

pytestmark = pytest.mark.e2e


def services(repository: StubRepositoryService | None = None) -> CliServices:
    return CliServices(
        version="0.0.0-test",
        cancellation=CancellationToken(),
        environment_checks=[lambda: CheckResult("git", True, "ok")],
        config_dump={},
        repository=repository or StubRepositoryService(),
        knowledge=StubKnowledgeService(),
        investigation=StubInvestigationService(),
        evaluation=StubEvaluationService(),
    )


class TestFetch:
    def test_reports_the_pinned_commit(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert run(services(), ["repo", "fetch", "https://example.com/a/b.git"]) == 0
        assert DEFAULT_SHA in capsys.readouterr().out

    def test_progress_goes_to_stderr_and_report_to_stdout(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        run(services(), ["repo", "fetch", "https://example.com/a/b.git"])
        captured = capsys.readouterr()
        assert "acquiring" in captured.err
        assert "acquiring" not in captured.out

    def test_quiet_suppresses_progress(self, capsys: pytest.CaptureFixture[str]) -> None:
        run(services(), ["repo", "fetch", "https://example.com/a/b.git", "--quiet"])
        assert "acquiring" not in capsys.readouterr().err

    def test_json_output_is_pure_and_versioned(self, capsys: pytest.CaptureFixture[str]) -> None:
        run(services(), ["repo", "fetch", "https://example.com/a/b.git", "--format", "json"])
        document = json.loads(capsys.readouterr().out)
        assert document["commit_sha"] == DEFAULT_SHA
        assert document["format_version"] == 1

    def test_ref_and_offline_flags_reach_the_service(self) -> None:
        stub = StubRepositoryService()
        run(
            services(stub),
            ["repo", "fetch", "https://example.com/a/b.git", "--ref", "v1.0", "--offline"],
        )
        assert stub.calls == [("https://example.com/a/b.git", "v1.0", True)]


class TestInspect:
    def test_terminal_output_summarizes_the_map(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert run(services(), ["repo", "inspect", "https://example.com/a/b.git"]) == 0
        out = capsys.readouterr().out
        assert "Python" in out
        assert "secret-like" in out

    def test_json_carries_snapshot_and_manifest(self, capsys: pytest.CaptureFixture[str]) -> None:
        run(services(), ["repo", "inspect", "https://example.com/a/b.git", "--format", "json"])
        document = json.loads(capsys.readouterr().out)
        assert document["snapshot"]["commit_sha"] == DEFAULT_SHA
        assert document["manifest"]["languages"] == {"Python": 2, "Markdown": 1}

    def test_markdown_output_is_rendered(self, capsys: pytest.CaptureFixture[str]) -> None:
        run(
            services(),
            ["repo", "inspect", "https://example.com/a/b.git", "--format", "markdown"],
        )
        out = capsys.readouterr().out
        assert out.startswith("# Repository map")
        assert "| Language | Files |" in out


class TestStatus:
    def test_lists_snapshots(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert run(services(), ["repo", "status"]) == 0
        assert DEFAULT_SHA[:12] in capsys.readouterr().out


class TestExitCodes:
    def test_acquisition_failure_exits_three(self, capsys: pytest.CaptureFixture[str]) -> None:
        stub = StubRepositoryService(
            error=AcquisitionError("host key verification failed", remediation="add the host")
        )
        assert run(services(stub), ["repo", "fetch", "https://example.com/a/b.git"]) == 3
        captured = capsys.readouterr()
        assert "host key verification failed" in captured.err
        assert captured.out == ""

    def test_policy_denial_exits_six(self) -> None:
        stub = StubRepositoryService(error=PolicyDeniedError("repository too large"))
        assert run(services(stub), ["repo", "fetch", "https://example.com/a/b.git"]) == 6

    def test_missing_argument_exits_two(self) -> None:
        assert run(services(), ["repo", "fetch"]) == 2
