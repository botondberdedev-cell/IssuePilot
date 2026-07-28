"""``issuepilot feedback`` end to end."""

from __future__ import annotations

import json

import pytest

from issuepilot.adapters.cli.app import run
from issuepilot.adapters.cli.services import CheckResult, CliServices
from issuepilot.shared_kernel.cancellation import CancellationToken
from tests.support.fakes.services import (
    StubEvaluationService,
    StubFeedbackService,
    StubInvestigationService,
    StubKnowledgeService,
    StubRepositoryService,
    sample_draft,
)

pytestmark = pytest.mark.e2e

RUN = "01RUN00000000000000000000"


def services(feedback: StubFeedbackService | None = None) -> CliServices:
    return CliServices(
        version="0.0.0-test",
        cancellation=CancellationToken(),
        environment_checks=[lambda: CheckResult("git", True, "ok")],
        config_dump={},
        repository=StubRepositoryService(),
        knowledge=StubKnowledgeService(),
        investigation=StubInvestigationService(),
        evaluation=StubEvaluationService(),
        feedback=feedback or StubFeedbackService(),
    )


def test_accept_is_recorded(capsys: pytest.CaptureFixture[str]) -> None:
    stub = StubFeedbackService()
    assert run(services(stub), ["feedback", "accept", RUN]) == 0
    assert stub.recorded == [(RUN, "accept", "")]
    assert "accepted" in capsys.readouterr().out


def test_reject_carries_the_note(capsys: pytest.CaptureFixture[str]) -> None:
    stub = StubFeedbackService()
    run(services(stub), ["feedback", "reject", RUN, "--note", "cited the wrong file"])
    assert stub.recorded == [(RUN, "reject", "cited the wrong file")]


def test_correct_requires_a_note() -> None:
    """A correction with no content is not a correction."""
    assert run(services(), ["feedback", "correct", RUN]) == 2


def test_correct_with_a_note_is_recorded() -> None:
    stub = StubFeedbackService()
    code = run(services(stub), ["feedback", "correct", RUN, "--note", "it was the state machine"])
    assert code == 0
    assert stub.recorded == [(RUN, "correct", "it was the state machine")]


def test_export_emits_pasteable_draft_cases(capsys: pytest.CaptureFixture[str]) -> None:
    stub = StubFeedbackService([sample_draft()])
    assert run(services(stub), ["feedback", "export"]) == 0
    line = capsys.readouterr().out.strip()
    payload = json.loads(line)
    assert payload["issue"] == "Refunds remain pending after a retry."
    assert "TODO" in payload["expected_paths"][0]


def test_export_json_format(capsys: pytest.CaptureFixture[str]) -> None:
    stub = StubFeedbackService([sample_draft()])
    run(services(stub), ["feedback", "export", "--format", "json"])
    assert json.loads(capsys.readouterr().out)[0]["category"] == "bug-location"


def test_export_with_nothing_to_export_says_so(capsys: pytest.CaptureFixture[str]) -> None:
    assert run(services(), ["feedback", "export"]) == 0
    assert "no rejections or corrections" in capsys.readouterr().out
