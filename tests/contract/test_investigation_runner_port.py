"""Contract suite for InvestigationRunnerPort."""

from __future__ import annotations

import pytest

from issuepilot.evaluation.application.ports import InvestigationRunnerPort
from issuepilot.evaluation.domain.scoring import ScoredReport
from tests.support.fakes.evaluation import ScriptedCaseRunner, sample_case


@pytest.fixture(params=["fake"])
def runner(request: pytest.FixtureRequest) -> InvestigationRunnerPort:
    return ScriptedCaseRunner()


def test_running_a_case_yields_a_scorable_report(
    runner: InvestigationRunnerPort,
) -> None:
    report = runner.run_case(sample_case())
    assert isinstance(report, ScoredReport)
    assert report.commit_sha


def test_the_report_carries_claims_and_citations(
    runner: InvestigationRunnerPort,
) -> None:
    report = runner.run_case(sample_case())
    assert report.claims
    assert report.citations


def test_a_failing_case_raises_rather_than_returning_junk() -> None:
    runner = ScriptedCaseRunner(failing={"case-1"})
    with pytest.raises(RuntimeError):
        runner.run_case(sample_case("case-1"))
