from __future__ import annotations

from datetime import UTC, datetime

import pytest

from issuepilot.repository.domain.manifest import RepositoryManifest
from issuepilot.repository.domain.snapshot import (
    AcquisitionOptions,
    RepositorySnapshot,
    SnapshotState,
    SnapshotTransitionError,
)
from issuepilot.repository.domain.values import CommitSha, RepositoryRef
from issuepilot.shared_kernel.ids import SnapshotId, new_ulid

SHA = CommitSha("a" * 40)
OTHER_SHA = CommitSha("b" * 40)
ACQUIRED_AT = datetime(2026, 7, 28, tzinfo=UTC)


def manifest(sha: CommitSha = SHA) -> RepositoryManifest:
    return RepositoryManifest(
        commit_sha=sha, requested_ref=RepositoryRef("main"), included=(), excluded=()
    )


def pending() -> RepositorySnapshot:
    return RepositorySnapshot(
        snapshot_id=SnapshotId(new_ulid()),
        locator_fingerprint="fp-1",
        requested_ref=RepositoryRef("main"),
        options=AcquisitionOptions(history_depth=100),
    )


def ready() -> RepositorySnapshot:
    return (
        pending()
        .begin_acquisition()
        .complete(commit_sha=SHA, root_path="/snap", manifest=manifest(), acquired_at=ACQUIRED_AT)
    )


class TestLifecycle:
    def test_happy_path_reaches_ready(self) -> None:
        snapshot = ready()
        assert snapshot.state is SnapshotState.READY
        assert snapshot.is_ready
        assert snapshot.pinned_sha() == SHA

    def test_transitions_do_not_mutate_the_original(self) -> None:
        start = pending()
        start.begin_acquisition()
        assert start.state is SnapshotState.PENDING

    def test_failure_records_a_reason(self) -> None:
        failed = pending().begin_acquisition().fail("host key verification failed")
        assert failed.state is SnapshotState.FAILED
        assert failed.failure_reason == "host key verification failed"


class TestIllegalTransitions:
    def test_cannot_complete_without_acquiring(self) -> None:
        with pytest.raises(SnapshotTransitionError, match="expected acquiring"):
            pending().complete(
                commit_sha=SHA,
                root_path="/snap",
                manifest=manifest(),
                acquired_at=ACQUIRED_AT,
            )

    def test_cannot_begin_acquisition_twice(self) -> None:
        acquiring = pending().begin_acquisition()
        with pytest.raises(SnapshotTransitionError, match="expected pending"):
            acquiring.begin_acquisition()

    def test_ready_is_terminal(self) -> None:
        snapshot = ready()
        with pytest.raises(SnapshotTransitionError, match="terminal"):
            snapshot.fail("too late")
        with pytest.raises(SnapshotTransitionError, match="expected pending"):
            snapshot.begin_acquisition()

    def test_failed_is_terminal(self) -> None:
        failed = pending().fail("nope")
        with pytest.raises(SnapshotTransitionError, match="terminal"):
            failed.fail("again")


class TestReadyInvariants:
    def _ready_kwargs(self) -> dict[str, object]:
        return {
            "snapshot_id": SnapshotId(new_ulid()),
            "locator_fingerprint": "fp-1",
            "requested_ref": RepositoryRef("main"),
            "options": AcquisitionOptions(history_depth=10),
            "state": SnapshotState.READY,
            "commit_sha": SHA,
            "root_path": "/snap",
            "manifest": manifest(),
            "acquired_at": ACQUIRED_AT,
        }

    def test_ready_requires_resolved_sha(self) -> None:
        kwargs = self._ready_kwargs() | {"commit_sha": None}
        with pytest.raises(ValueError, match="resolved commit sha"):
            RepositorySnapshot(**kwargs)  # type: ignore[arg-type]

    def test_ready_requires_manifest(self) -> None:
        kwargs = self._ready_kwargs() | {"manifest": None}
        with pytest.raises(ValueError, match="resolved commit sha"):
            RepositorySnapshot(**kwargs)  # type: ignore[arg-type]

    def test_manifest_must_match_the_pinned_commit(self) -> None:
        kwargs = self._ready_kwargs() | {"manifest": manifest(OTHER_SHA)}
        with pytest.raises(ValueError, match="different commit"):
            RepositorySnapshot(**kwargs)  # type: ignore[arg-type]

    def test_ready_requires_aware_timestamp(self) -> None:
        kwargs = self._ready_kwargs() | {"acquired_at": None}
        with pytest.raises(ValueError, match="aware acquisition timestamp"):
            RepositorySnapshot(**kwargs)  # type: ignore[arg-type]

    def test_failed_requires_a_reason(self) -> None:
        with pytest.raises(ValueError, match="requires a reason"):
            RepositorySnapshot(
                snapshot_id=SnapshotId(new_ulid()),
                locator_fingerprint="fp-1",
                requested_ref=RepositoryRef("main"),
                options=AcquisitionOptions(history_depth=10),
                state=SnapshotState.FAILED,
            )

    def test_fingerprint_is_required(self) -> None:
        with pytest.raises(ValueError, match="locator fingerprint"):
            RepositorySnapshot(
                snapshot_id=SnapshotId(new_ulid()),
                locator_fingerprint="",
                requested_ref=RepositoryRef("main"),
                options=AcquisitionOptions(history_depth=10),
            )


class TestPinnedSha:
    def test_pinned_sha_unavailable_before_ready(self) -> None:
        with pytest.raises(SnapshotTransitionError, match="no resolved commit"):
            pending().pinned_sha()


class TestAcquisitionOptions:
    def test_defaults_exclude_submodules_and_lfs(self) -> None:
        options = AcquisitionOptions(history_depth=1)
        assert not options.include_submodules
        assert not options.include_lfs

    def test_history_depth_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            AcquisitionOptions(history_depth=0)
