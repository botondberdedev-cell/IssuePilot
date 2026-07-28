"""Wires the repository context and translates CLI primitives into domain types.

This module is one of the few allowed to see both the CLI's vocabulary
(strings, ints, flags) and the domain's (validated value objects). Doing the
translation here is what lets the CLI stay free of domain imports and the
domain stay free of CLI concerns.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from pathlib import Path

from issuepilot.repository.application.dto import ManifestDTO, SnapshotDTO
from issuepilot.repository.application.public import RepositoryFacade
from issuepilot.repository.application.use_cases.acquire_snapshot import (
    AcquireSnapshot,
    AcquireSnapshotCommand,
)
from issuepilot.repository.domain.limits import SizeBudget
from issuepilot.repository.domain.manifest import FileEligibilityPolicy
from issuepilot.repository.domain.snapshot import AcquisitionOptions
from issuepilot.repository.domain.values import RepositoryLocator, RepositoryRef
from issuepilot.repository.infrastructure.git_acquirer import GitRepositoryAcquirer
from issuepilot.repository.infrastructure.snapshot_reader import SnapshotReader
from issuepilot.repository.infrastructure.snapshot_repo import SqliteSnapshotStore
from issuepilot.repository.infrastructure.workspace import WorkspaceLayout
from issuepilot.shared_kernel.cancellation import CancellationToken
from issuepilot.shared_kernel.clock import Clock
from issuepilot.shared_kernel.errors import UsageError
from issuepilot.shared_kernel.events import EventBus
from issuepilot.shared_kernel.ids import IdGenerator


def build_repository_facade(
    *,
    connection: sqlite3.Connection,
    workspace_dir: Path,
    max_file_bytes: int,
    max_total_bytes: int,
    ids: IdGenerator,
    clock: Clock,
    bus: EventBus,
    cancellation: CancellationToken,
) -> RepositoryFacade:
    layout = WorkspaceLayout(workspace_dir)
    acquirer = GitRepositoryAcquirer(layout, cancellation=cancellation)
    store = SqliteSnapshotStore(connection)
    use_case = AcquireSnapshot(
        acquirer=acquirer,
        store=store,
        eligibility=FileEligibilityPolicy(max_file_bytes=max_file_bytes),
        size_budget=SizeBudget(max_total_bytes=max_total_bytes),
        ids=ids,
        clock=clock,
        bus=bus,
    )
    return RepositoryFacade(use_case, SnapshotReader(), store)


class RepositoryServiceAdapter:
    """Presents the repository facade in the primitives the CLI speaks."""

    def __init__(self, facade: RepositoryFacade, default_depth: int) -> None:
        self._facade = facade
        self._default_depth = default_depth

    def acquire(
        self,
        locator: str,
        *,
        ref: str | None = None,
        depth: int = 100,
        offline: bool = False,
        allow_local_path: bool = False,
    ) -> SnapshotDTO:
        return self._facade.acquire(self._command(locator, ref, depth, offline, allow_local_path))

    def inspect(
        self,
        locator: str,
        *,
        ref: str | None = None,
        depth: int = 100,
        offline: bool = False,
        allow_local_path: bool = False,
    ) -> tuple[SnapshotDTO, ManifestDTO]:
        return self._facade.inspect(self._command(locator, ref, depth, offline, allow_local_path))

    def recent_snapshots(self, limit: int = 20) -> Sequence[SnapshotDTO]:
        return self._facade.recent_snapshots(limit)

    def _command(
        self,
        locator: str,
        ref: str | None,
        depth: int,
        offline: bool,
        allow_local_path: bool,
    ) -> AcquireSnapshotCommand:
        """Validate CLI input, reporting rejections as usage errors (exit 2).

        A malformed locator or ref is the user's typo, not an acquisition
        failure, so it must not be reported as one.
        """
        try:
            parsed_locator = RepositoryLocator.parse(locator, allow_local_path=allow_local_path)
        except ValueError as exc:
            raise UsageError(
                f"invalid repository locator: {exc}",
                remediation="use https://host/owner/repo.git, user@host:owner/repo.git, "
                "or an absolute path with --allow-local-path",
            ) from exc

        parsed_ref: RepositoryRef | None = None
        if ref is not None:
            try:
                parsed_ref = RepositoryRef(ref)
            except ValueError as exc:
                raise UsageError(f"invalid ref: {exc}") from exc

        try:
            options = AcquisitionOptions(history_depth=depth or self._default_depth)
        except ValueError as exc:
            raise UsageError(f"invalid --depth: {exc}") from exc

        return AcquireSnapshotCommand(
            locator=parsed_locator, ref=parsed_ref, options=options, offline=offline
        )
