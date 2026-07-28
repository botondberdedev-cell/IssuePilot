from __future__ import annotations

from collections.abc import Sequence

from issuepilot.repository.application.ports import (
    AcquiredSnapshot,
    SnapshotRecord,
    TrackedFile,
)
from issuepilot.repository.domain.snapshot import AcquisitionOptions
from issuepilot.repository.domain.values import (
    CommitSha,
    LineRange,
    RelativeRepoPath,
    RepositoryLocator,
    RepositoryRef,
)
from issuepilot.shared_kernel.errors import AcquisitionError, PolicyDeniedError
from issuepilot.shared_kernel.ids import SnapshotId


class FakeRepositoryAcquirer:
    """Serves pre-seeded snapshots keyed by ref; no git, no filesystem."""

    def __init__(self, default_branch: str = "main") -> None:
        self._by_ref: dict[str, AcquiredSnapshot] = {}
        self._default_branch = default_branch
        self.acquired: list[tuple[str, str, bool]] = []

    def seed(
        self,
        ref: str,
        *,
        commit_sha: str,
        root_path: str = "/fake/snapshot",
        files: Sequence[TrackedFile] = (),
    ) -> AcquiredSnapshot:
        snapshot = AcquiredSnapshot(
            commit_sha=CommitSha(commit_sha), root_path=root_path, files=tuple(files)
        )
        self._by_ref[ref] = snapshot
        return snapshot

    def acquire(
        self,
        locator: RepositoryLocator,
        ref: RepositoryRef,
        options: AcquisitionOptions,
        *,
        offline: bool = False,
    ) -> AcquiredSnapshot:
        self.acquired.append((locator.raw, ref.value, offline))
        snapshot = self._by_ref.get(ref.value)
        if snapshot is None:
            raise AcquisitionError(
                f"fake acquirer has no snapshot for {ref.value!r}",
                remediation="seed() the ref in the test",
            )
        return snapshot

    def default_ref(self, locator: RepositoryLocator) -> RepositoryRef:
        return RepositoryRef(self._default_branch)


class FakeSnapshotReader:
    """In-memory file contents, with the same confinement contract as the
    real reader: anything registered as escaping is refused, not returned."""

    def __init__(self) -> None:
        self._files: dict[tuple[str, str], str] = {}
        self._escaping: set[tuple[str, str]] = set()

    def add_file(self, root_path: str, path: str, content: str) -> None:
        self._files[(root_path, path)] = content

    def add_escaping_path(self, root_path: str, path: str) -> None:
        self._escaping.add((root_path, path))

    def contains(self, root_path: str, path: RelativeRepoPath) -> bool:
        key = (root_path, path.value)
        return key not in self._escaping and key in self._files

    def line_count(self, root_path: str, path: RelativeRepoPath) -> int:
        return len(self._lines(root_path, path))

    def read_slice(self, root_path: str, path: RelativeRepoPath, line_range: LineRange) -> str:
        lines = self._lines(root_path, path)
        return "".join(lines[line_range.start - 1 : line_range.end])

    def _lines(self, root_path: str, path: RelativeRepoPath) -> list[str]:
        key = (root_path, path.value)
        if key in self._escaping:
            raise PolicyDeniedError(f"path escapes the repository snapshot: {path.value}")
        if key not in self._files:
            raise FileNotFoundError(f"{path.value} is not a file in this snapshot")
        return self._files[key].splitlines(keepends=True)


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

    def list_recent(self, limit: int = 20) -> Sequence[SnapshotRecord]:
        # Snapshot ids are ULIDs, so reverse id order is reverse time order.
        ordered = sorted(self._records.values(), key=lambda r: r.snapshot_id, reverse=True)
        return tuple(ordered[:limit])
