"""``issuepilot eval`` end to end — the CI contract.

The exit status *is* the merge decision, so these tests pin it.
"""

from __future__ import annotations

import json

import pytest

from issuepilot.adapters.cli.app import run
from issuepilot.adapters.cli.services import CheckResult, CliServices
from issuepilot.shared_kernel.cancellation import CancellationToken
from tests.support.fakes.services import (
    StubEvaluationService,
    StubInvestigationService,
    StubKnowledgeService,
    StubRepositoryService,
    failing_suite,
)

pytestmark = pytest.mark.e2e


def services(evaluation: StubEvaluationService | None = None) -> CliServices:
    return CliServices(
        version="0.0.0-test",
        cancellation=CancellationToken(),
        environment_checks=[lambda: CheckResult("git", True, "ok")],
        config_dump={},
        repository=StubRepositoryService(),
        knowledge=StubKnowledgeService(),
        investigation=StubInvestigationService(),
        evaluation=evaluation or StubEvaluationService(),
    )


def test_a_passing_suite_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert run(services(), ["eval", "run"]) == 0
    assert "PASSED" in capsys.readouterr().out


def test_a_failing_gate_exits_seven(capsys: pytest.CaptureFixture[str]) -> None:
    """This is the whole point: CI needs no output parsing."""
    evaluation = StubEvaluationService(failing_suite())
    assert run(services(evaluation), ["eval", "run"]) == 7
    captured = capsys.readouterr()
    assert "FAILED" in captured.out
    assert "quality gate" in captured.err


def test_failing_cases_are_named(capsys: pytest.CaptureFixture[str]) -> None:
    run(services(StubEvaluationService(failing_suite())), ["eval", "run"])
    out = capsys.readouterr().out
    assert "case-b" in out
    assert "citation-validity" in out


def test_json_output_carries_metrics_and_thresholds(capsys: pytest.CaptureFixture[str]) -> None:
    run(services(), ["eval", "run", "--format", "json"])
    document = json.loads(capsys.readouterr().out)
    assert document["format_version"] == 1
    assert document["passed"] is True
    assert document["metrics"]["citation-validity"] == 1.0
    assert any(t["metric"] == "citation-validity" for t in document["thresholds"])


def test_json_output_records_the_dataset_hash(capsys: pytest.CaptureFixture[str]) -> None:
    """Lineage: a result is only comparable to another from the same cases."""
    run(services(), ["eval", "run", "--format", "json"])
    assert json.loads(capsys.readouterr().out)["dataset_hash"]


def test_progress_reports_each_case_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    run(services(StubEvaluationService(failing_suite())), ["eval", "run"])
    err = capsys.readouterr().err
    assert "ok   case-a" in err
    assert "FAIL case-b" in err


def test_datasets_are_listed(capsys: pytest.CaptureFixture[str]) -> None:
    assert run(services(), ["eval", "datasets"]) == 0
    assert "core" in capsys.readouterr().out
