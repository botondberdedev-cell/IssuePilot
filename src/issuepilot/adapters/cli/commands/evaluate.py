"""``issuepilot eval`` — run the evaluation suite and apply the quality gate.

A failing gate exits 7, so CI needs no special parsing: the command's exit
status *is* the merge decision.
"""

from __future__ import annotations

import json
from typing import Annotated

import typer

from issuepilot.adapters.cli.console import Console, OutputFormat
from issuepilot.adapters.cli.render import evaluation as render
from issuepilot.adapters.cli.services import CliServices
from issuepilot.shared_kernel.errors import QualityGateError

FormatOption = Annotated[OutputFormat, typer.Option("--format", help="Output format.")]


def register(app: typer.Typer, services: CliServices) -> None:
    eval_app = typer.Typer(no_args_is_help=True, help="Measure investigation quality.")
    app.add_typer(eval_app, name="eval")

    @eval_app.command("run")
    def run_suite(
        dataset: Annotated[str, typer.Argument(help="Dataset name.")] = "core",
        output_format: FormatOption = OutputFormat.TERMINAL,
        quiet: Annotated[bool, typer.Option("--quiet")] = False,
    ) -> None:
        """Run every case and apply the gate. Exits 7 if the gate fails."""
        console = Console(quiet=quiet)
        console.progress(f"evaluating {dataset} ...")
        result = services.evaluation.run(
            dataset,
            on_case=lambda score: console.progress(
                f"  {'ok  ' if score.passed else 'FAIL'} {score.case_id}"
            ),
        )

        if output_format is OutputFormat.JSON:
            console.out(json.dumps(render.suite_json(result), indent=2))
        else:
            console.out(render.suite_terminal(result, console))

        if not result.passed:
            raise QualityGateError(
                f"quality gate failed on: {', '.join(result.blocking_metrics)}",
                remediation="inspect the failing cases above, or run with --format json",
            )

    @eval_app.command("datasets")
    def list_datasets() -> None:
        """List the available evaluation datasets."""
        console = Console()
        names = services.evaluation.available_datasets()
        console.out("\n".join(names) if names else "no datasets found")
