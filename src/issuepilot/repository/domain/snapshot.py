"""The repository snapshot aggregate.

A snapshot is the unit of reproducibility: once it reaches ``READY`` it is
bound to one fully-resolved commit SHA and one manifest, and it never
changes. Branch names are informational after resolution — every citation
downstream is anchored to the SHA recorded here.

Transitions return new instances rather than mutating, so an illegal
transition is a caught error instead of a corrupted aggregate.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum, unique

from issuepilot.repository.domain.manifest import RepositoryManifest
from issuepilot.repository.domain.values import CommitSha, RepositoryRef
from issuepilot.shared_kernel.ids import SnapshotId


@unique
class SnapshotState(Enum):
    PENDING = "pending"
    ACQUIRING = "acquiring"
    READY = "ready"
    FAILED = "failed"

    @property
    def is_terminal(self) -> bool:
        return self in (SnapshotState.READY, SnapshotState.FAILED)


class SnapshotTransitionError(Exception):
    """An illegal state transition was attempted on a snapshot."""


@dataclass(frozen=True, slots=True)
class AcquisitionOptions:
    """What the user asked to be included; recorded for reproducibility."""

    history_depth: int
    include_submodules: bool = False
    include_lfs: bool = False

    def __post_init__(self) -> None:
        if self.history_depth < 1:
            raise ValueError(f"history depth must be positive, got {self.history_depth}")


@dataclass(frozen=True, slots=True)
class RepositorySnapshot:
    snapshot_id: SnapshotId
    locator_fingerprint: str
    requested_ref: RepositoryRef
    options: AcquisitionOptions
    state: SnapshotState = SnapshotState.PENDING
    commit_sha: CommitSha | None = None
    root_path: str | None = None
    manifest: RepositoryManifest | None = None
    acquired_at: datetime | None = None
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.locator_fingerprint:
            raise ValueError("a snapshot requires a locator fingerprint")
        if self.state is SnapshotState.READY:
            if self.commit_sha is None or self.root_path is None or self.manifest is None:
                raise ValueError(
                    "a READY snapshot requires a resolved commit sha, root path, and manifest"
                )
            if self.manifest.commit_sha != self.commit_sha:
                raise ValueError("snapshot manifest belongs to a different commit")
            if self.acquired_at is None or self.acquired_at.tzinfo is None:
                raise ValueError("a READY snapshot requires an aware acquisition timestamp")
        if self.state is SnapshotState.FAILED and not self.failure_reason:
            raise ValueError("a FAILED snapshot requires a reason")

    def begin_acquisition(self) -> RepositorySnapshot:
        self._require_state(SnapshotState.PENDING, "begin acquisition")
        return replace(self, state=SnapshotState.ACQUIRING)

    def complete(
        self,
        *,
        commit_sha: CommitSha,
        root_path: str,
        manifest: RepositoryManifest,
        acquired_at: datetime,
    ) -> RepositorySnapshot:
        self._require_state(SnapshotState.ACQUIRING, "complete acquisition")
        return replace(
            self,
            state=SnapshotState.READY,
            commit_sha=commit_sha,
            root_path=root_path,
            manifest=manifest,
            acquired_at=acquired_at,
        )

    def fail(self, reason: str) -> RepositorySnapshot:
        if self.state.is_terminal:
            raise SnapshotTransitionError(
                f"cannot fail a snapshot already in terminal state {self.state.value}"
            )
        return replace(self, state=SnapshotState.FAILED, failure_reason=reason)

    def _require_state(self, expected: SnapshotState, action: str) -> None:
        if self.state is not expected:
            raise SnapshotTransitionError(
                f"cannot {action}: snapshot is {self.state.value}, expected {expected.value}"
            )

    @property
    def is_ready(self) -> bool:
        return self.state is SnapshotState.READY

    def pinned_sha(self) -> CommitSha:
        """The resolved commit; only meaningful once READY."""
        if self.commit_sha is None:
            raise SnapshotTransitionError(
                f"snapshot has no resolved commit while {self.state.value}"
            )
        return self.commit_sha
