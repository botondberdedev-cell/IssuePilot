"""Repository-context domain events."""

from __future__ import annotations

from dataclasses import dataclass

from issuepilot.shared_kernel.events import DomainEvent


@dataclass(frozen=True, slots=True, kw_only=True)
class RepositorySnapshotCreated(DomainEvent):
    snapshot_id: str
    commit_sha: str
    requested_ref: str
    locator_fingerprint: str


@dataclass(frozen=True, slots=True, kw_only=True)
class RepositoryAcquisitionFailed(DomainEvent):
    locator_fingerprint: str
    reason_category: str
