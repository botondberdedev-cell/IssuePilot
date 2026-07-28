from __future__ import annotations

from io import StringIO

import pytest

from issuepilot.adapters.cli.console import Console


def make_console(
    *, quiet: bool = False, color: bool | None = None
) -> tuple[Console, StringIO, StringIO]:
    stdout, stderr = StringIO(), StringIO()
    return Console(quiet=quiet, color=color, stdout=stdout, stderr=stderr), stdout, stderr


def test_deliverable_goes_to_stdout_only() -> None:
    console, stdout, stderr = make_console(color=False)
    console.out("the report")
    assert stdout.getvalue() == "the report\n"
    assert stderr.getvalue() == ""


def test_progress_goes_to_stderr_only() -> None:
    console, stdout, stderr = make_console(color=False)
    console.progress("working...")
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == "working...\n"


def test_quiet_suppresses_progress_but_not_errors() -> None:
    console, _, stderr = make_console(quiet=True, color=False)
    console.progress("working...")
    console.error("failed", remediation="try again")
    output = stderr.getvalue()
    assert "working" not in output
    assert "error: failed" in output
    assert "hint: try again" in output


def test_no_color_env_disables_ansi(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    console, _, stderr = make_console()  # color auto-detected
    console.error("plain")
    assert "\x1b[" not in stderr.getvalue()


def test_styling_when_color_enabled() -> None:
    console, _, _ = make_console(color=True)
    assert console.style("x", "red") == "\x1b[31mx\x1b[0m"
