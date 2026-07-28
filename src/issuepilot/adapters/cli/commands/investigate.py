"""``issuepilot investigate`` — the product's main command.

Issue text can come from ``--issue``, a file, or stdin (``--issue-file -``),
because an issue is usually already written down somewhere.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import typer

from issuepilot.adapters.cli.console import Console, OutputFormat
from issuepilot.adapters.cli.render import investigation as render
from issuepilot.adapters.cli.services import CliServices
from issuepilot.investigation.application.dto import ReportDTO
from issuepilot.shared_kernel.errors import UsageError

LocatorArgument = Annotated[str, typer.Argument(help="Repository URL or path.")]
FormatOption = Annotated[OutputFormat, typer.Option("--format", help="Output format.")]
QuietOption = Annotated[bool, typer.Option("--quiet", help="Suppress progress messages.")]


def register(app: typer.Typer, services: CliServices) -> None:
    @app.command()
    def investigate(
        locator: LocatorArgument,
        issue: Annotated[str | None, typer.Option("--issue", help="The issue text.")] = None,
        issue_file: Annotated[
            str | None,
            typer.Option("--issue-file", help="Read the issue from a file, or '-' for stdin."),
        ] = None,
        ref: Annotated[str | None, typer.Option("--ref", help="Branch, tag, or commit.")] = None,
        allow_local_path: Annotated[
            bool, typer.Option("--allow-local-path", help="Permit a local repository path.")
        ] = False,
        max_steps: Annotated[
            int | None, typer.Option("--max-steps", help="Investigation step budget.")
        ] = None,
        output: Annotated[
            str | None, typer.Option("--output", help="Also write the report to this file.")
        ] = None,
        output_format: FormatOption = OutputFormat.TERMINAL,
        quiet: QuietOption = False,
    ) -> None:
        """Investigate an issue and produce an evidence-linked report."""
        console = Console(quiet=quiet)
        issue_text = _read_issue(issue, issue_file)

        console.progress(f"acquiring {locator} ...")
        snapshot = services.repository.acquire(locator, ref=ref, allow_local_path=allow_local_path)
        if not services.knowledge.is_indexed(snapshot.commit_sha):
            console.progress(f"indexing {snapshot.commit_sha[:12]} ...")
        services.knowledge.build_index(snapshot.commit_sha, snapshot.root_path)

        console.progress(f"investigating at {snapshot.commit_sha[:12]} ...")
        report = services.investigation.investigate(
            issue_text,
            snapshot.commit_sha,
            snapshot.root_path,
            max_steps=max_steps,
            on_step=lambda step: console.progress(f"  step {step.index}: {step.tool}"),
        )

        rendered = _render(report, output_format, console)
        console.out(rendered)
        if output:
            Path(output).write_text(rendered + "\n", encoding="utf-8")
            console.progress(f"written to {output}")

    @app.command()
    def runs(
        limit: Annotated[int, typer.Option("--limit", help="How many to list.")] = 10,
        output_format: FormatOption = OutputFormat.TERMINAL,
    ) -> None:
        """List recent investigations."""
        console = Console()
        reports = services.investigation.recent_reports(limit)
        if output_format is OutputFormat.JSON:
            console.out(json.dumps([render.report_json(r) for r in reports], indent=2))
        else:
            console.out(render.report_list_terminal(reports, console))


def _render(report: ReportDTO, output_format: OutputFormat, console: Console) -> str:
    if output_format is OutputFormat.JSON:
        return json.dumps(render.report_json(report), indent=2)
    if output_format is OutputFormat.MARKDOWN:
        return render.report_markdown(report)
    return render.report_terminal(report, console)


def _read_issue(issue: str | None, issue_file: str | None) -> str:
    if issue and issue_file:
        raise UsageError("pass either --issue or --issue-file, not both")
    if issue:
        return issue
    if issue_file == "-":
        text = sys.stdin.read()
        if not text.strip():
            raise UsageError("no issue text arrived on stdin")
        return text
    if issue_file:
        path = Path(issue_file)
        if not path.is_file():
            raise UsageError(f"issue file not found: {issue_file}")
        return path.read_text(encoding="utf-8")
    raise UsageError(
        "no issue supplied",
        remediation="pass --issue 'text', --issue-file path, or --issue-file - for stdin",
    )
