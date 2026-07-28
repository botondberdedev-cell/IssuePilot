from __future__ import annotations

import pytest

from issuepilot.adapters.git.client import GitInvocationError, git_version, run_git

pytestmark = pytest.mark.integration


def test_run_git_version_succeeds() -> None:
    result = run_git(["--version"], timeout_seconds=10)
    assert result.ok
    assert result.stdout.startswith("git version")
    assert result.stderr == ""


def test_failed_command_returns_typed_result_not_exception() -> None:
    result = run_git(["not-a-real-subcommand"], timeout_seconds=10)
    assert not result.ok
    assert result.returncode != 0


def test_missing_binary_raises_invocation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "")
    with pytest.raises(GitInvocationError, match="not found"):
        run_git(["--version"], timeout_seconds=10)


def test_git_version_helper() -> None:
    version = git_version()
    assert version is not None
    assert version.startswith("git version")
