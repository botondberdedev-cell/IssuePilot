"""``issuepilot doctor`` — verify the environment is ready.

Exit code 0 when every check passes, 2 otherwise (the environment is not
usable as configured).
"""

from __future__ import annotations

import json
from typing import Annotated

import typer

from issuepilot.adapters.cli.console import Console, OutputFormat
from issuepilot.adapters.cli.services import CliServices


def register(app: typer.Typer, services: CliServices) -> None:
    @app.command()
    def doctor(
        output_format: Annotated[
            OutputFormat, typer.Option("--format", help="Output format.")
        ] = OutputFormat.TERMINAL,
        quiet: Annotated[bool, typer.Option("--quiet", help="Suppress progress messages.")] = False,
    ) -> None:
        """Check git, Ollama, models, and the local database environment."""
        console = Console(quiet=quiet)
        results = [check() for check in services.environment_checks]
        all_ok = all(r.ok for r in results)

        if output_format is OutputFormat.JSON:
            document = {
                "version": services.version,
                "ok": all_ok,
                "checks": [
                    {
                        "name": r.name,
                        "ok": r.ok,
                        "detail": r.detail,
                        "remediation": r.remediation,
                    }
                    for r in results
                ],
            }
            console.out(json.dumps(document, indent=2))
        else:
            console.out(f"issuepilot {services.version}")
            for r in results:
                mark = console.style("ok", "green") if r.ok else console.style("FAIL", "red")
                console.out(f"  [{mark}] {r.name}: {r.detail}")
                if not r.ok and r.remediation:
                    console.out(f"         hint: {r.remediation}")

        if not all_ok:
            raise typer.Exit(code=2)
