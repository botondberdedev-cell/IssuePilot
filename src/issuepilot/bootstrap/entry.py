"""Process entry point: compose the application, then hand over to the CLI.

This is the top of the dependency graph — the only place (with
``bootstrap.wiring``) allowed to see every context and adapter at once.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from importlib import metadata

from issuepilot.adapters.cli.app import run
from issuepilot.adapters.cli.console import Console
from issuepilot.adapters.cli.services import CliServices
from issuepilot.adapters.eventbus import SqliteOutboxEventBus
from issuepilot.adapters.sqlite.connection import connect
from issuepilot.adapters.sqlite.migrator import migrate
from issuepilot.bootstrap.config import AppConfig, load_config, redacted_dump
from issuepilot.bootstrap.wiring.diagnostics import build_environment_checks
from issuepilot.bootstrap.wiring.investigation import (
    InvestigationServiceAdapter,
    build_investigation_facade,
)
from issuepilot.bootstrap.wiring.knowledge import (
    KnowledgeServiceAdapter,
    RepositorySourceTranslator,
    build_knowledge_facade,
)
from issuepilot.bootstrap.wiring.repository import (
    RepositoryServiceAdapter,
    build_repository_facade,
)
from issuepilot.shared_kernel.cancellation import CancellationToken
from issuepilot.shared_kernel.clock import SystemClock
from issuepilot.shared_kernel.errors import IssuePilotError, exit_code_for
from issuepilot.shared_kernel.ids import UlidGenerator

DATABASE_FILENAME = "issuepilot.db"


def open_database(config: AppConfig) -> sqlite3.Connection:
    """Open the workspace database, applying any pending migrations."""
    connection = connect(config.workspace_dir / DATABASE_FILENAME)
    migrate(connection)
    return connection


def build_services(
    config: AppConfig,
    connection: sqlite3.Connection,
    *,
    semantic_enabled: bool = True,
) -> CliServices:
    """Compose the application from an already-open database.

    The caller owns the connection and closes it — ``run_cli`` below for the
    CLI, the fixture for a test. Composition deliberately does not acquire
    resources it cannot release.

    ``semantic_enabled`` is wired, not probed: composition must not make
    network calls. If Ollama is down the failure surfaces at the point of
    use as exit code 4, and ``doctor`` is what reports it up front.
    """
    resolved_config = config
    resolved_connection = connection

    cancellation = CancellationToken()
    ids = UlidGenerator()
    clock = SystemClock()
    bus = SqliteOutboxEventBus(resolved_connection)

    repository_facade = build_repository_facade(
        connection=resolved_connection,
        workspace_dir=resolved_config.workspace_dir,
        max_file_bytes=resolved_config.repository.max_file_bytes,
        max_total_bytes=resolved_config.repository.max_total_bytes,
        ids=ids,
        clock=clock,
        bus=bus,
        cancellation=cancellation,
    )

    source = RepositorySourceTranslator(repository_facade)
    knowledge_facade = build_knowledge_facade(
        connection=resolved_connection,
        workspace_dir=resolved_config.workspace_dir,
        source=source,
        ids=ids,
        clock=clock,
        bus=bus,
        ollama_url=resolved_config.models.ollama_url,
        embedding_model=resolved_config.models.embedding,
        semantic_enabled=semantic_enabled,
    )

    snapshot_roots: dict[str, str] = {}
    investigation_facade = build_investigation_facade(
        connection=resolved_connection,
        repository=repository_facade,
        knowledge=knowledge_facade,
        ids=ids,
        clock=clock,
        bus=bus,
        ollama_url=resolved_config.models.ollama_url,
        chat_model=resolved_config.models.chat,
        keep_alive=resolved_config.models.keep_alive,
        snapshot_roots=snapshot_roots,
    )

    return CliServices(
        version=_version(),
        cancellation=cancellation,
        environment_checks=build_environment_checks(resolved_config),
        config_dump=redacted_dump(resolved_config),
        repository=RepositoryServiceAdapter(
            repository_facade, resolved_config.repository.history_depth
        ),
        knowledge=KnowledgeServiceAdapter(knowledge_facade, source),
        investigation=InvestigationServiceAdapter(
            investigation_facade,
            snapshot_roots,
            resolved_config.investigation.max_steps,
            resolved_config.investigation.timeout_seconds,
        ),
    )


def _version() -> str:
    try:
        return metadata.version("issuepilot")
    except metadata.PackageNotFoundError:  # pragma: no cover - editable installs
        return "0.0.0+unknown"


def run_cli(argv: Sequence[str] | None = None) -> int:
    try:
        config = load_config()
        connection = open_database(config)
    except IssuePilotError as exc:
        Console().error(str(exc), remediation=exc.remediation)
        return exit_code_for(exc)
    try:
        return run(build_services(config, connection), argv)
    finally:
        connection.close()


def main() -> None:
    raise SystemExit(run_cli())
