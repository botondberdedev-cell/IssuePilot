"""``issuepilot index`` and ``issuepilot search``.

Both take a repository locator rather than a bare commit: acquiring is cheap
once the snapshot is cached, and it guarantees the index and the search are
talking about the same pinned commit.
"""

from __future__ import annotations

import json
from typing import Annotated

import typer

from issuepilot.adapters.cli.console import Console, OutputFormat
from issuepilot.adapters.cli.render import knowledge as render
from issuepilot.adapters.cli.services import CliServices

LocatorArgument = Annotated[str, typer.Argument(help="Repository URL or path.")]
RefOption = Annotated[str | None, typer.Option("--ref", help="Branch, tag, or commit.")]
FormatOption = Annotated[OutputFormat, typer.Option("--format", help="Output format.")]
LocalPathOption = Annotated[
    bool, typer.Option("--allow-local-path", help="Permit a local filesystem repository path.")
]
QuietOption = Annotated[bool, typer.Option("--quiet", help="Suppress progress messages.")]


def register(app: typer.Typer, services: CliServices) -> None:
    @app.command()
    def index(
        locator: LocatorArgument,
        ref: RefOption = None,
        allow_local_path: LocalPathOption = False,
        rebuild: Annotated[
            bool, typer.Option("--rebuild", help="Rebuild even if already indexed.")
        ] = False,
        output_format: FormatOption = OutputFormat.TERMINAL,
        quiet: QuietOption = False,
    ) -> None:
        """Build the searchable index for a repository snapshot."""
        console = Console(quiet=quiet)
        console.progress(f"acquiring {locator} ...")
        snapshot = services.repository.acquire(locator, ref=ref, allow_local_path=allow_local_path)
        console.progress(f"indexing {snapshot.commit_sha[:12]} ...")
        stats = services.knowledge.build_index(
            snapshot.commit_sha, snapshot.root_path, rebuild=rebuild
        )
        if output_format is OutputFormat.JSON:
            console.out(json.dumps(render.stats_json(stats), indent=2))
        else:
            console.out(render.stats_terminal(stats, console))

    @app.command()
    def search(
        locator: LocatorArgument,
        query: Annotated[str, typer.Argument(help="What to look for.")],
        ref: RefOption = None,
        allow_local_path: LocalPathOption = False,
        limit: Annotated[int, typer.Option("--limit", help="Maximum results.")] = 10,
        output_format: FormatOption = OutputFormat.TERMINAL,
        quiet: QuietOption = False,
    ) -> None:
        """Search a repository, indexing it first if necessary."""
        console = Console(quiet=quiet)
        snapshot = services.repository.acquire(locator, ref=ref, allow_local_path=allow_local_path)
        if not services.knowledge.is_indexed(snapshot.commit_sha):
            console.progress(f"indexing {snapshot.commit_sha[:12]} ...")
            services.knowledge.build_index(snapshot.commit_sha, snapshot.root_path)

        hits = services.knowledge.search(snapshot.commit_sha, query, limit=limit)
        if output_format is OutputFormat.JSON:
            console.out(json.dumps(render.hits_json(hits), indent=2))
        elif output_format is OutputFormat.MARKDOWN:
            console.out(render.hits_markdown(hits))
        else:
            console.out(render.hits_terminal(hits, console))
