"""Acquisition against system git and the on-disk workspace.

Sequence, all of it under the repository's inter-process lock:

1. Reuse a published snapshot when its commit is already materialized.
2. Otherwise fetch the requested ref into the shared bare object cache.
3. Resolve the ref to a full commit SHA — from here on, the SHA is the
   identity; the branch name is only provenance.
4. Materialize a detached worktree into a staging directory.
5. Publish it with one atomic rename.

Offline mode skips step 2 entirely and fails if nothing usable is cached,
rather than quietly answering about a different commit than the user asked
for.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from issuepilot.adapters.git import porcelain
from issuepilot.adapters.git.porcelain import GitError, GitErrorCategory
from issuepilot.repository.application.ports import AcquiredSnapshot, TrackedFile
from issuepilot.repository.domain.snapshot import AcquisitionOptions
from issuepilot.repository.domain.values import (
    CommitSha,
    RelativeRepoPath,
    RepositoryLocator,
    RepositoryRef,
)
from issuepilot.repository.infrastructure.workspace import (
    WorkspaceLayout,
    make_read_only,
    publish_atomically,
    repository_lock,
)
from issuepilot.shared_kernel.cancellation import NEVER_CANCELLED, CancellationToken
from issuepilot.shared_kernel.errors import AcquisitionError

_CATEGORY_IS_RETRYABLE = {
    GitErrorCategory.NETWORK,
    GitErrorCategory.TIMEOUT,
    GitErrorCategory.UNAVAILABLE,
}


class GitRepositoryAcquirer:
    def __init__(
        self,
        layout: WorkspaceLayout,
        *,
        cancellation: CancellationToken = NEVER_CANCELLED,
    ) -> None:
        self._layout = layout
        self._cancellation = cancellation

    def default_ref(self, locator: RepositoryLocator) -> RepositoryRef:
        try:
            return RepositoryRef(porcelain.remote_head_ref(locator.raw))
        except GitError as exc:
            raise _as_acquisition_error(exc) from exc

    def acquire(
        self,
        locator: RepositoryLocator,
        ref: RepositoryRef,
        options: AcquisitionOptions,
        *,
        offline: bool = False,
    ) -> AcquiredSnapshot:
        fingerprint = locator.fingerprint()
        self._layout.prepare(fingerprint)
        cache = self._layout.object_cache(fingerprint)

        with repository_lock(self._layout.lock_file(fingerprint)):
            self._cancellation.raise_if_cancelled()
            porcelain.init_bare_cache(cache)

            sha = self._resolve(cache, locator, ref, options, offline=offline)
            snapshot_path = self._layout.snapshot_path(fingerprint, sha.value)

            if snapshot_path.is_dir():
                return AcquiredSnapshot(
                    commit_sha=sha,
                    root_path=str(snapshot_path),
                    files=self._tracked_files(cache, sha),
                    reused_cache=True,
                )

            self._cancellation.raise_if_cancelled()
            staging = self._layout.new_staging_path(fingerprint)
            try:
                porcelain.create_worktree(cache, sha.value, staging)
                # Detach the tree from git *before* publishing: the snapshot
                # is inert content, and git must not hold a live reference to
                # a directory we are about to rename.
                _strip_worktree_metadata(staging)
                make_read_only(staging)
                publish_atomically(staging, snapshot_path)
                porcelain.prune_worktrees(cache)
            except GitError as exc:
                shutil.rmtree(staging, ignore_errors=True)
                raise _as_acquisition_error(exc) from exc
            except BaseException:
                shutil.rmtree(staging, ignore_errors=True)
                raise

            return AcquiredSnapshot(
                commit_sha=sha,
                root_path=str(snapshot_path),
                files=self._tracked_files(cache, sha),
                reused_cache=False,
            )

    def _resolve(
        self,
        cache: Path,
        locator: RepositoryLocator,
        ref: RepositoryRef,
        options: AcquisitionOptions,
        *,
        offline: bool,
    ) -> CommitSha:
        if offline:
            return self._resolve_offline(cache, ref)
        try:
            porcelain.fetch_ref(cache, locator.raw, ref.value, depth=options.history_depth)
            return CommitSha(porcelain.resolve_ref(cache, "FETCH_HEAD"))
        except GitError as exc:
            raise _as_acquisition_error(exc) from exc

    def _resolve_offline(self, cache: Path, ref: RepositoryRef) -> CommitSha:
        """Resolve strictly from cached objects; never widen the request."""
        try:
            return CommitSha(porcelain.resolve_ref(cache, ref.value))
        except GitError as exc:
            raise AcquisitionError(
                f"offline: {ref.value!r} is not available in the local cache",
                remediation="run once without --offline to populate the cache",
            ) from exc

    def _tracked_files(self, cache: Path, sha: CommitSha) -> tuple[TrackedFile, ...]:
        try:
            entries = porcelain.list_tree(cache, sha.value)
        except GitError as exc:
            raise _as_acquisition_error(exc) from exc
        files: list[TrackedFile] = []
        for entry in entries:
            try:
                path = RelativeRepoPath(entry.path)
            except ValueError:
                # git tracked something our path rules reject; skipping is
                # safer than widening the rules for one odd repository.
                continue
            files.append(
                TrackedFile(path=path, size_bytes=entry.size_bytes, is_binary=entry.is_binary)
            )
        return tuple(files)


def _strip_worktree_metadata(root: Path) -> None:
    """Remove the ``.git`` link file so the snapshot is inert content only."""
    marker = root / ".git"
    if marker.is_file():
        marker.unlink()
    elif marker.is_dir():
        shutil.rmtree(marker, ignore_errors=True)


def _as_acquisition_error(exc: GitError) -> AcquisitionError:
    """Map a git failure onto the CLI's acquisition contract (exit code 3)."""
    detail = str(exc)
    if exc.category in _CATEGORY_IS_RETRYABLE:
        detail = f"{detail} (transient)"
    return AcquisitionError(detail, remediation=exc.remediation)
