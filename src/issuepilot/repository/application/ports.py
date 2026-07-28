"""Ports required by the repository context's use cases.

Ports are ``typing.Protocol``s, structurally implemented by infrastructure
adapters and by fakes in the test suite. Every port declared here must have
a fake and a contract suite (enforced by ``tests/arch/test_conventions.py``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from issuepilot.repository.domain.values import CommitSha, RepositoryRef
from issuepilot.shared_kernel.ids import SnapshotId


@dataclass(frozen=True, slots=True)
class SnapshotRecord:
    """Persistent record of a materialized snapshot."""

    snapshot_id: SnapshotId
    locator_fingerprint: str
    requested_ref: RepositoryRef
    commit_sha: CommitSha
    root_path: str


class SnapshotStorePort(Protocol):
    def put(self, record: SnapshotRecord) -> None: ...

    def get(self, snapshot_id: SnapshotId) -> SnapshotRecord | None: ...

    def find_by_commit(self, locator_fingerprint: str, sha: CommitSha) -> SnapshotRecord | None: ...
