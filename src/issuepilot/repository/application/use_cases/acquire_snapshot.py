"""Acquire a repository snapshot and build its manifest.

The use case owns the *decisions* — which ref, which files are eligible,
when the aggregate may transition — and delegates the mechanics of fetching
and materializing to ports. That split is what lets the whole flow be tested
without a git process.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from issuepilot.repository.application.ports import (
    AcquiredSnapshot,
    RepositoryAcquirerPort,
    SnapshotRecord,
    SnapshotStorePort,
)
from issuepilot.repository.domain.events import (
    RepositoryAcquisitionFailed,
    RepositorySnapshotCreated,
)
from issuepilot.repository.domain.manifest import (
    ExcludedFile,
    FileEligibilityPolicy,
    FileEntry,
    RepositoryManifest,
    detect_language,
)
from issuepilot.repository.domain.snapshot import AcquisitionOptions, RepositorySnapshot
from issuepilot.repository.domain.values import RepositoryLocator, RepositoryRef
from issuepilot.shared_kernel.clock import Clock
from issuepilot.shared_kernel.errors import IssuePilotError
from issuepilot.shared_kernel.events import EventBus
from issuepilot.shared_kernel.ids import EventId, IdGenerator, SnapshotId

DEFAULT_HISTORY_DEPTH = 100


@dataclass(frozen=True, slots=True)
class AcquireSnapshotCommand:
    locator: RepositoryLocator
    ref: RepositoryRef | None = None
    """None means "whatever the remote's default branch is"; it is resolved
    to a concrete ref before the snapshot records it."""
    options: AcquisitionOptions = field(
        default_factory=lambda: AcquisitionOptions(history_depth=DEFAULT_HISTORY_DEPTH)
    )
    offline: bool = False


class AcquireSnapshot:
    def __init__(
        self,
        *,
        acquirer: RepositoryAcquirerPort,
        store: SnapshotStorePort,
        eligibility: FileEligibilityPolicy,
        ids: IdGenerator,
        clock: Clock,
        bus: EventBus,
    ) -> None:
        self._acquirer = acquirer
        self._store = store
        self._eligibility = eligibility
        self._ids = ids
        self._clock = clock
        self._bus = bus

    def execute(self, command: AcquireSnapshotCommand) -> RepositorySnapshot:
        fingerprint = command.locator.fingerprint()
        ref = command.ref or self._acquirer.default_ref(command.locator)

        snapshot = RepositorySnapshot(
            snapshot_id=SnapshotId(self._ids.new_id()),
            locator_fingerprint=fingerprint,
            requested_ref=ref,
            options=command.options,
        ).begin_acquisition()

        try:
            acquired = self._acquirer.acquire(
                command.locator, ref, command.options, offline=command.offline
            )
        except IssuePilotError as exc:
            self._publish_failure(fingerprint, snapshot, exc)
            raise

        manifest = self._build_manifest(acquired, ref)
        ready = snapshot.complete(
            commit_sha=acquired.commit_sha,
            root_path=acquired.root_path,
            manifest=manifest,
            acquired_at=self._clock.now(),
        )

        self._store.put(
            SnapshotRecord(
                snapshot_id=ready.snapshot_id,
                locator_fingerprint=fingerprint,
                requested_ref=ref,
                commit_sha=acquired.commit_sha,
                root_path=acquired.root_path,
            )
        )
        self._bus.publish(
            RepositorySnapshotCreated(
                event_id=EventId(self._ids.new_id()),
                occurred_at=self._clock.now(),
                aggregate_id=ready.snapshot_id,
                snapshot_id=ready.snapshot_id,
                commit_sha=acquired.commit_sha.value,
                requested_ref=ref.value,
                locator_fingerprint=fingerprint,
            )
        )
        return ready

    def _build_manifest(self, acquired: AcquiredSnapshot, ref: RepositoryRef) -> RepositoryManifest:
        included: list[FileEntry] = []
        excluded: list[ExcludedFile] = []
        for tracked in acquired.files:
            reason = self._eligibility.evaluate(
                tracked.path, tracked.size_bytes, is_binary=tracked.is_binary
            )
            if reason is None:
                included.append(
                    FileEntry(
                        path=tracked.path,
                        size_bytes=tracked.size_bytes,
                        language=detect_language(tracked.path),
                    )
                )
            else:
                excluded.append(ExcludedFile(path=tracked.path, reason=reason))
        return RepositoryManifest(
            commit_sha=acquired.commit_sha,
            requested_ref=ref,
            included=tuple(included),
            excluded=tuple(excluded),
        )

    def _publish_failure(
        self, fingerprint: str, snapshot: RepositorySnapshot, exc: IssuePilotError
    ) -> None:
        self._bus.publish(
            RepositoryAcquisitionFailed(
                event_id=EventId(self._ids.new_id()),
                occurred_at=self._clock.now(),
                aggregate_id=snapshot.snapshot_id,
                locator_fingerprint=fingerprint,
                reason_category=exc.category.value,
            )
        )
