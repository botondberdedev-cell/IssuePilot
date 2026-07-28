from __future__ import annotations

from issuepilot.repository.application.ports import SnapshotRecord
from issuepilot.repository.domain.values import CommitSha
from issuepilot.shared_kernel.ids import SnapshotId


class InMemorySnapshotStore:
    def __init__(self) -> None:
        self._records: dict[str, SnapshotRecord] = {}

    def put(self, record: SnapshotRecord) -> None:
        self._records[record.snapshot_id] = record

    def get(self, snapshot_id: SnapshotId) -> SnapshotRecord | None:
        return self._records.get(snapshot_id)

    def find_by_commit(self, locator_fingerprint: str, sha: CommitSha) -> SnapshotRecord | None:
        for record in self._records.values():
            if record.locator_fingerprint == locator_fingerprint and record.commit_sha == sha:
                return record
        return None
