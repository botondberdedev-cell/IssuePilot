"""``issuepilot feedback`` — record whether a report was actually useful.

This is the only signal that distinguishes "the tool cited real code" from
"the tool was right". Corrections become draft evaluation cases, so the suite
grows from real failures rather than from imagination.
"""

from __future__ import annotations

import json
from typing import Annotated

import typer

from issuepilot.adapters.cli.console import Console, OutputFormat
from issuepilot.adapters.cli.services import CliServices

RunArgument = Annotated[str, typer.Argument(help="The run id, from `issuepilot runs`.")]
NoteOption = Annotated[str, typer.Option("--note", help="What was wrong, in your words.")]


def register(app: typer.Typer, services: CliServices) -> None:
    feedback_app = typer.Typer(no_args_is_help=True, help="Record report quality.")
    app.add_typer(feedback_app, name="feedback")

    @feedback_app.command()
    def accept(run_id: RunArgument) -> None:
        """Mark a report as useful and correct."""
        console = Console()
        services.feedback.accept(run_id)
        console.out(f"recorded: {run_id} accepted")

    @feedback_app.command()
    def reject(run_id: RunArgument, note: NoteOption = "") -> None:
        """Mark a report as not useful."""
        console = Console()
        services.feedback.reject(run_id, note)
        console.out(f"recorded: {run_id} rejected")

    @feedback_app.command()
    def correct(run_id: RunArgument, note: NoteOption) -> None:
        """Record what the right answer was. Requires a note."""
        console = Console()
        services.feedback.correct(run_id, note)
        console.out(f"recorded: {run_id} corrected")

    @feedback_app.command("export")
    def export_cases(
        output_format: Annotated[
            OutputFormat, typer.Option("--format", help="Output format.")
        ] = OutputFormat.TERMINAL,
    ) -> None:
        """Export rejections and corrections as draft evaluation cases."""
        console = Console()
        drafts = services.feedback.export_candidates()
        if not drafts:
            console.out("no rejections or corrections to export")
            return
        if output_format is OutputFormat.JSON:
            console.out(json.dumps([json.loads(d.to_jsonl_stub()) for d in drafts], indent=2))
        else:
            console.out("\n".join(d.to_jsonl_stub() for d in drafts))
