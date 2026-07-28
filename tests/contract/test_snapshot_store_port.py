"""Contract suite for SnapshotStorePort (SQLite adapter joins in v0.1)."""

from __future__ import annotations

import pytest

from issuepilot.repository.application.ports import SnapshotRecord, SnapshotStorePort
from issuepilot.repository.domain.values import CommitSha, RepositoryRef
from issuepilot.shared_kernel.ids import SnapshotId, new_ulid
from tests.support.fakes.snapshot_store import InMemorySnapshotStore

SHA_A = CommitSha("a" * 40)


@pytest.fixture(params=["fake"])
def store(request: pytest.FixtureRequest) -> SnapshotStorePort:
    return InMemorySnapshotStore()


def _record(fingerprint: str = "fp-1") -> SnapshotRecord:
    return SnapshotRecord(
        snapshot_id=SnapshotId(new_ulid()),
        locator_fingerprint=fingerprint,
        requested_ref=RepositoryRef("main"),
        commit_sha=SHA_A,
        root_path="/tmp/snap",
    )


def test_put_get_roundtrip(store: SnapshotStorePort) -> None:
    record = _record()
    store.put(record)
    assert store.get(record.snapshot_id) == record


def test_get_missing_returns_none(store: SnapshotStorePort) -> None:
    assert store.get(SnapshotId(new_ulid())) is None


def test_find_by_commit_matches_fingerprint_and_sha(store: SnapshotStorePort) -> None:
    record = _record("fp-match")
    store.put(record)
    assert store.find_by_commit("fp-match", SHA_A) == record
    assert store.find_by_commit("fp-other", SHA_A) is None
    assert store.find_by_commit("fp-match", CommitSha("b" * 40)) is None
