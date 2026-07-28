"""The service surface the CLI is wired with.

The CLI is a driving adapter: it parses arguments into *primitives*, calls
one service method, and renders the returned DTO. It never constructs domain
objects — that translation happens in ``bootstrap.wiring``, which is the only
place allowed to see both sides. This is what keeps the architecture contract
"CLI depends only on application facades" true in practice rather than by
convention.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from issuepilot.repository.application.dto import ManifestDTO, SnapshotDTO
from issuepilot.shared_kernel.cancellation import CancellationToken
from issuepilot.shared_kernel.hashing import Json


@dataclass(frozen=True, slots=True)
class CheckResult:
    """Outcome of one environment check run by ``issuepilot doctor``."""

    name: str
    ok: bool
    detail: str
    remediation: str | None = None


type EnvironmentCheck = Callable[[], CheckResult]


class RepositoryService(Protocol):
    """Repository operations, expressed in primitives the CLI already has."""

    def acquire(
        self,
        locator: str,
        *,
        ref: str | None = None,
        depth: int = 100,
        offline: bool = False,
        allow_local_path: bool = False,
    ) -> SnapshotDTO: ...

    def inspect(
        self,
        locator: str,
        *,
        ref: str | None = None,
        depth: int = 100,
        offline: bool = False,
        allow_local_path: bool = False,
    ) -> tuple[SnapshotDTO, ManifestDTO]: ...

    def recent_snapshots(self, limit: int = 20) -> Sequence[SnapshotDTO]: ...


@dataclass(frozen=True, slots=True)
class CliServices:
    version: str
    cancellation: CancellationToken
    environment_checks: Sequence[EnvironmentCheck]
    config_dump: Mapping[str, Json]
    """Effective non-secret configuration, already redacted, for ``config show``."""
    repository: RepositoryService
