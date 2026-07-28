"""The repository context's public facade.

Other contexts never import repository internals; they reach this facade
through a translator wired in ``bootstrap``. ``verify_citation`` is the
method the whole evidence guarantee rests on: it answers whether a claimed
path, line range, and commit actually exist in a snapshot we materialized.
"""

from __future__ import annotations

from collections.abc import Sequence

from issuepilot.repository.application.dto import FileSliceDTO, ManifestDTO, SnapshotDTO
from issuepilot.repository.application.ports import SnapshotReaderPort, SnapshotStorePort
from issuepilot.repository.application.use_cases.acquire_snapshot import (
    AcquireSnapshot,
    AcquireSnapshotCommand,
)
from issuepilot.repository.domain.snapshot import RepositorySnapshot
from issuepilot.repository.domain.values import LineRange, RelativeRepoPath
from issuepilot.shared_kernel.errors import PolicyDeniedError

_MANIFEST_SAMPLE_SIZE = 20


class RepositoryFacade:
    def __init__(
        self,
        acquire: AcquireSnapshot,
        reader: SnapshotReaderPort,
        store: SnapshotStorePort,
    ) -> None:
        self._acquire = acquire
        self._reader = reader
        self._store = store

    def acquire(self, command: AcquireSnapshotCommand) -> SnapshotDTO:
        snapshot = self._acquire.execute(command)
        return _to_dto(snapshot)

    def inspect(self, command: AcquireSnapshotCommand) -> tuple[SnapshotDTO, ManifestDTO]:
        snapshot = self._acquire.execute(command)
        manifest = snapshot.manifest
        if manifest is None:  # pragma: no cover - a READY snapshot always has one
            raise ValueError("a ready snapshot must carry a manifest")
        return _to_dto(snapshot), ManifestDTO(
            commit_sha=manifest.commit_sha.value,
            requested_ref=manifest.requested_ref.value,
            included_count=manifest.included_count,
            excluded_count=manifest.excluded_count,
            total_bytes=manifest.total_bytes,
            languages=manifest.language_distribution(),
            exclusions=manifest.exclusion_counts(),
            sample_paths=tuple(
                entry.path.value for entry in manifest.included[:_MANIFEST_SAMPLE_SIZE]
            ),
        )

    def read_slice(
        self, root_path: str, commit_sha: str, path: str, start_line: int, end_line: int
    ) -> FileSliceDTO:
        relative = RelativeRepoPath(path)
        line_range = LineRange(start_line, end_line)
        text = self._reader.read_slice(root_path, relative, line_range)
        return FileSliceDTO(
            path=path,
            start_line=start_line,
            end_line=end_line,
            commit_sha=commit_sha,
            text=text,
        )

    def verify_citation(self, root_path: str, path: str, start_line: int, end_line: int) -> bool:
        """Whether this exact location exists in this snapshot.

        Returns False rather than raising for every kind of miss — malformed
        path, missing file, escaping symlink, range past end of file — because
        the caller's question is only ever "may this be cited?".
        """
        try:
            relative = RelativeRepoPath(path)
            line_range = LineRange(start_line, end_line)
        except ValueError:
            return False
        try:
            if not self._reader.contains(root_path, relative):
                return False
            return self._reader.line_count(root_path, relative) >= line_range.end
        except (PolicyDeniedError, OSError):
            return False

    def recent_snapshots(self, limit: int = 20) -> Sequence[SnapshotDTO]:
        return tuple(
            SnapshotDTO(
                snapshot_id=record.snapshot_id,
                commit_sha=record.commit_sha.value,
                requested_ref=record.requested_ref.value,
                locator_fingerprint=record.locator_fingerprint,
                root_path=record.root_path,
            )
            for record in self._store.list_recent(limit)
        )


def _to_dto(snapshot: RepositorySnapshot) -> SnapshotDTO:
    return SnapshotDTO(
        snapshot_id=snapshot.snapshot_id,
        commit_sha=snapshot.pinned_sha().value,
        requested_ref=snapshot.requested_ref.value,
        locator_fingerprint=snapshot.locator_fingerprint,
        root_path=snapshot.root_path or "",
    )
