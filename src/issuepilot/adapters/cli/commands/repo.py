"""``issuepilot repo`` — acquire and inspect repository snapshots."""

from __future__ import annotations

import json
from typing import Annotated

import typer

from issuepilot.adapters.cli.console import Console, OutputFormat
from issuepilot.adapters.cli.render import repo as render
from issuepilot.adapters.cli.services import CliServices

RefOption = Annotated[
    str | None,
    typer.Option("--ref", help="Branch, tag, or commit. Defaults to the remote's default."),
]
FormatOption = Annotated[OutputFormat, typer.Option("--format", help="Output format.")]
OfflineOption = Annotated[
    bool, typer.Option("--offline", help="Use only cached objects; never reach the network.")
]
LocalPathOption = Annotated[
    bool, typer.Option("--allow-local-path", help="Permit a local filesystem repository path.")
]
DepthOption = Annotated[int, typer.Option("--depth", help="History depth to fetch.")]
QuietOption = Annotated[bool, typer.Option("--quiet", help="Suppress progress messages.")]
LocatorArgument = Annotated[str, typer.Argument(help="Repository URL or path.")]


def register(app: typer.Typer, services: CliServices) -> None:
    repo_app = typer.Typer(no_args_is_help=True, help="Acquire and inspect repositories.")
    app.add_typer(repo_app, name="repo")

    @repo_app.command()
    def fetch(
        locator: LocatorArgument,
        ref: RefOption = None,
        depth: DepthOption = 100,
        offline: OfflineOption = False,
        allow_local_path: LocalPathOption = False,
        output_format: FormatOption = OutputFormat.TERMINAL,
        quiet: QuietOption = False,
    ) -> None:
        """Fetch a repository and pin an immutable snapshot."""
        console = Console(quiet=quiet)
        console.progress(f"acquiring {locator} ...")
        snapshot = services.repository.acquire(
            locator, ref=ref, depth=depth, offline=offline, allow_local_path=allow_local_path
        )
        if output_format is OutputFormat.JSON:
            console.out(json.dumps(render.snapshot_json(snapshot), indent=2))
        else:
            console.out(render.snapshot_terminal(snapshot, console))

    @repo_app.command()
    def inspect(
        locator: LocatorArgument,
        ref: RefOption = None,
        depth: DepthOption = 100,
        offline: OfflineOption = False,
        allow_local_path: LocalPathOption = False,
        output_format: FormatOption = OutputFormat.TERMINAL,
        quiet: QuietOption = False,
    ) -> None:
        """Map a repository: languages, file counts, and why files were skipped."""
        console = Console(quiet=quiet)
        console.progress(f"inspecting {locator} ...")
        snapshot, manifest = services.repository.inspect(
            locator, ref=ref, depth=depth, offline=offline, allow_local_path=allow_local_path
        )
        if output_format is OutputFormat.JSON:
            console.out(
                json.dumps(
                    {
                        "snapshot": render.snapshot_json(snapshot),
                        "manifest": render.manifest_json(manifest),
                    },
                    indent=2,
                )
            )
        elif output_format is OutputFormat.MARKDOWN:
            console.out(render.manifest_markdown(snapshot, manifest))
        else:
            console.out(render.manifest_terminal(snapshot, manifest, console))

    @repo_app.command()
    def status(
        limit: Annotated[int, typer.Option("--limit", help="How many to list.")] = 10,
        output_format: FormatOption = OutputFormat.TERMINAL,
    ) -> None:
        """List recently acquired snapshots."""
        console = Console()
        snapshots = services.repository.recent_snapshots(limit)
        if output_format is OutputFormat.JSON:
            console.out(json.dumps([render.snapshot_json(s) for s in snapshots], indent=2))
        else:
            console.out(render.snapshot_list_terminal(snapshots, console))
