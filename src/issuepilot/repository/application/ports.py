"""Ports required by the repository context's use cases.

Ports are ``typing.Protocol``s, structurally implemented by infrastructure
adapters and by fakes in the test suite. Every port declared here must have
a fake and a contract suite (enforced by ``tests/arch/test_conventions.py``).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from issuepilot.repository.domain.snapshot import AcquisitionOptions
from issuepilot.repository.domain.values import (
    CommitSha,
    LineRange,
    RelativeRepoPath,
    RepositoryLocator,
    RepositoryRef,
)
from issuepilot.shared_kernel.ids import SnapshotId


@dataclass(frozen=True, slots=True)
class TrackedFile:
    """One file git tracks at a commit, before eligibility is decided."""

    path: RelativeRepoPath
    size_bytes: int
    is_binary: bool


@dataclass(frozen=True, slots=True)
class AcquiredSnapshot:
    """The raw result of acquisition: a pinned commit and materialized tree."""

    commit_sha: CommitSha
    root_path: str
    files: tuple[TrackedFile, ...]
    reused_cache: bool = False


@dataclass(frozen=True, slots=True)
class SnapshotRecord:
    """Persistent record of a materialized snapshot."""

    snapshot_id: SnapshotId
    locator_fingerprint: str
    requested_ref: RepositoryRef
    commit_sha: CommitSha
    root_path: str


class RepositoryAcquirerPort(Protocol):
    """Fetches a repository and materializes an immutable snapshot.

    Implementations own locking, caching, and atomic publication; the use
    case only cares that a returned snapshot is complete and pinned.
    """

    def acquire(
        self,
        locator: RepositoryLocator,
        ref: RepositoryRef,
        options: AcquisitionOptions,
        *,
        offline: bool = False,
    ) -> AcquiredSnapshot: ...

    def default_ref(self, locator: RepositoryLocator) -> RepositoryRef: ...


class SnapshotReaderPort(Protocol):
    """Bounded reads from a materialized snapshot.

    Implementations must confine every read to the snapshot root, so a
    symlink inside the repository cannot reach the wider filesystem.
    """

    def contains(self, root_path: str, path: RelativeRepoPath) -> bool: ...

    def line_count(self, root_path: str, path: RelativeRepoPath) -> int: ...

    def read_slice(self, root_path: str, path: RelativeRepoPath, line_range: LineRange) -> str: ...


class SnapshotStorePort(Protocol):
    def put(self, record: SnapshotRecord) -> None: ...

    def get(self, snapshot_id: SnapshotId) -> SnapshotRecord | None: ...

    def find_by_commit(self, locator_fingerprint: str, sha: CommitSha) -> SnapshotRecord | None: ...

    def list_recent(self, limit: int = 20) -> Sequence[SnapshotRecord]: ...
