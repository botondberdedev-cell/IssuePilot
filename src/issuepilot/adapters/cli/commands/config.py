"""``issuepilot config`` — show and validate the effective configuration."""

from __future__ import annotations

import json
from typing import Annotated

import typer

from issuepilot.adapters.cli.console import Console, OutputFormat
from issuepilot.adapters.cli.services import CliServices


def register(app: typer.Typer, services: CliServices) -> None:
    config_app = typer.Typer(no_args_is_help=True, help="Inspect configuration.")
    app.add_typer(config_app, name="config")

    @config_app.command()
    def show(
        output_format: Annotated[
            OutputFormat, typer.Option("--format", help="Output format.")
        ] = OutputFormat.JSON,
    ) -> None:
        """Print the effective non-secret configuration."""
        console = Console()
        document = json.dumps(dict(services.config_dump), indent=2, sort_keys=True)
        if output_format is OutputFormat.MARKDOWN:
            console.out(f"```json\n{document}\n```")
        else:
            console.out(document)

    @config_app.command()
    def validate() -> None:
        """Validate the configuration (loading it already validates every field)."""
        console = Console()
        console.out("configuration is valid")
