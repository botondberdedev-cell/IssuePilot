"""End-to-end CLI contract tests: exit codes, stdout/stderr separation, JSON."""

from __future__ import annotations

import json

import pytest

from issuepilot.adapters.cli.app import run
from issuepilot.adapters.cli.services import CheckResult, CliServices
from issuepilot.shared_kernel.cancellation import CancellationToken
from issuepilot.shared_kernel.errors import AcquisitionError
from tests.support.fakes.repository_service import StubRepositoryService

pytestmark = pytest.mark.e2e


def make_services(
    *,
    checks: list[CheckResult] | None = None,
    raising: Exception | None = None,
) -> CliServices:
    results = checks if checks is not None else [CheckResult("git", True, "git version 2.54.0")]

    def make_check(result: CheckResult) -> object:
        def check() -> CheckResult:
            if raising is not None:
                raise raising
            return result

        return check

    return CliServices(
        version="0.0.0-test",
        cancellation=CancellationToken(),
        environment_checks=[make_check(r) for r in results],  # type: ignore[misc]
        config_dump={"models": {"chat": "qwen3"}},
        repository=StubRepositoryService(),
    )


def test_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert run(make_services(), ["--help"]) == 0
    captured = capsys.readouterr()
    assert "issuepilot" in captured.out


def test_unknown_command_exits_two(capsys: pytest.CaptureFixture[str]) -> None:
    assert run(make_services(), ["frobnicate"]) == 2


def test_unknown_option_exits_two() -> None:
    assert run(make_services(), ["doctor", "--nope"]) == 2


def test_doctor_ok_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert run(make_services(), ["doctor"]) == 0
    captured = capsys.readouterr()
    assert "git" in captured.out


def test_doctor_failure_exits_two() -> None:
    failing = [CheckResult("ollama", False, "not reachable", remediation="start ollama")]
    assert run(make_services(checks=failing), ["doctor"]) == 2


def test_doctor_json_is_pure_and_valid(capsys: pytest.CaptureFixture[str]) -> None:
    assert run(make_services(), ["doctor", "--format", "json"]) == 0
    captured = capsys.readouterr()
    document = json.loads(captured.out)
    assert document["ok"] is True
    assert document["checks"][0]["name"] == "git"


def test_typed_error_maps_to_contract_exit_code(capsys: pytest.CaptureFixture[str]) -> None:
    services = make_services(raising=AcquisitionError("ssh auth failed", remediation="add key"))
    assert run(services, ["doctor"]) == 3
    captured = capsys.readouterr()
    assert "ssh auth failed" in captured.err
    assert "add key" in captured.err
    assert captured.out == ""


def test_config_show_emits_valid_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert run(make_services(), ["config", "show"]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"models": {"chat": "qwen3"}}


def test_config_validate_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert run(make_services(), ["config", "validate"]) == 0
