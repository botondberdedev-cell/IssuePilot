"""Process entry point: compose the application, then hand over to the CLI.

This is the top of the dependency graph — the only module allowed to see
every context and adapter at once (with ``bootstrap.wiring``).
"""

from __future__ import annotations

from collections.abc import Sequence
from importlib import metadata

from issuepilot.adapters.cli.app import run
from issuepilot.adapters.cli.console import Console
from issuepilot.adapters.cli.services import CliServices
from issuepilot.bootstrap.config import load_config, redacted_dump
from issuepilot.bootstrap.wiring.diagnostics import build_environment_checks
from issuepilot.shared_kernel.cancellation import CancellationToken
from issuepilot.shared_kernel.errors import IssuePilotError, exit_code_for


def build_services() -> CliServices:
    config = load_config()
    return CliServices(
        version=metadata.version("issuepilot"),
        cancellation=CancellationToken(),
        environment_checks=build_environment_checks(config),
        config_dump=redacted_dump(config),
    )


def run_cli(argv: Sequence[str] | None = None) -> int:
    try:
        services = build_services()
    except IssuePilotError as exc:
        Console().error(str(exc), remediation=exc.remediation)
        return exit_code_for(exc)
    return run(services, argv)


def main() -> None:
    raise SystemExit(run_cli())
