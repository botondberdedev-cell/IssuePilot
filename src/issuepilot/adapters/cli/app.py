"""Typer application factory and the single exception → exit-code boundary."""

from __future__ import annotations

import contextlib
import importlib
import signal
import sys
import types
from collections.abc import Sequence
from typing import Final

import click.exceptions
import typer

from issuepilot.adapters.cli.commands import config as config_cmd
from issuepilot.adapters.cli.commands import doctor as doctor_cmd
from issuepilot.adapters.cli.commands import evaluate as evaluate_cmd
from issuepilot.adapters.cli.commands import feedback as feedback_cmd
from issuepilot.adapters.cli.commands import index as index_cmd
from issuepilot.adapters.cli.commands import investigate as investigate_cmd
from issuepilot.adapters.cli.commands import repo as repo_cmd
from issuepilot.adapters.cli.console import Console
from issuepilot.adapters.cli.services import CliServices
from issuepilot.shared_kernel.errors import (
    EXIT_CODES,
    EXIT_SUCCESS,
    ErrorCategory,
    IssuePilotError,
    exit_code_for,
)


def _typer_click_exceptions() -> types.ModuleType:
    """Typer routes through a vendored click fork depending on the installed
    click version; the exit-code contract must hold for both."""
    try:
        return importlib.import_module("typer._click.exceptions")
    except ImportError:  # pragma: no cover - depends on installed typer/click combo
        return click.exceptions


_vendored = _typer_click_exceptions()
_EXIT_TYPES: Final = (click.exceptions.Exit, _vendored.Exit)
_USAGE_TYPES: Final = (click.exceptions.ClickException, _vendored.ClickException)
_ABORT_TYPES: Final = (click.exceptions.Abort, _vendored.Abort)


def create_app(services: CliServices) -> typer.Typer:
    app = typer.Typer(
        name="issuepilot",
        no_args_is_help=True,
        add_completion=False,
        help="Investigate repository issues locally, with evidence-linked reports.",
    )
    doctor_cmd.register(app, services)
    config_cmd.register(app, services)
    repo_cmd.register(app, services)
    index_cmd.register(app, services)
    investigate_cmd.register(app, services)
    evaluate_cmd.register(app, services)
    feedback_cmd.register(app, services)

    @app.callback()
    def _root() -> None:
        """Local-first repository investigation."""

    return app


def run(services: CliServices, argv: Sequence[str] | None = None) -> int:
    """Run the CLI; always returns an exit code from the documented contract."""
    _install_sigint_handler(services)
    console = Console()
    app = create_app(services)
    command = typer.main.get_command(app)
    try:
        # With standalone_mode=False, click RETURNS the code for Exit raised
        # inside commands (e.g. typer.Exit) instead of calling sys.exit.
        result = command.main(args=argv, prog_name="issuepilot", standalone_mode=False)
    except _EXIT_TYPES as exc:
        return int(exc.exit_code)
    except _USAGE_TYPES as exc:
        exc.show()
        return EXIT_CODES[ErrorCategory.USAGE]
    except _ABORT_TYPES:
        return EXIT_CODES[ErrorCategory.INTERRUPTED]
    except IssuePilotError as exc:
        console.error(str(exc), remediation=exc.remediation)
        return exit_code_for(exc)
    except KeyboardInterrupt:
        console.error("interrupted")
        return EXIT_CODES[ErrorCategory.INTERRUPTED]
    if isinstance(result, int):
        return result
    return EXIT_SUCCESS


def _install_sigint_handler(services: CliServices) -> None:
    """First Ctrl-C requests graceful cancellation; the second aborts hard."""

    def handler(signum: int, frame: types.FrameType | None) -> None:
        if services.cancellation.cancelled:
            raise KeyboardInterrupt
        services.cancellation.cancel()
        print(
            "\ncancelling — finishing the current step (Ctrl-C again to abort)",
            file=sys.stderr,
            flush=True,
        )

    # ValueError: not on the main thread (e.g. some test runners) — polling still works.
    with contextlib.suppress(ValueError):
        signal.signal(signal.SIGINT, handler)
