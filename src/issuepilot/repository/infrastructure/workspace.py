"""On-disk workspace: object caches, snapshots, locks, and safe reads.

Layout under the configured workspace directory::

    repositories/<fingerprint>/objects.git   bare object cache
    repositories/<fingerprint>/lock          inter-process lock
    snapshots/<fingerprint>/<sha>/           immutable materialized tree
    snapshots/<fingerprint>/.staging-<id>/   in-progress, never observed as ready

Two properties matter more than anything else here:

*Atomic publication.* A snapshot is materialized into a staging directory and
moved into place with a single rename. A crash mid-acquisition leaves debris
that is obviously incomplete, never a partial tree that looks ready.

*Confinement.* Repository content is untrusted. Every read resolves symlinks
and verifies the result is still inside the snapshot root, so a repository
cannot use a link to make the tool read (and then cite) ``/etc/passwd``.
"""

from __future__ import annotations

import fcntl
import os
import shutil
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from issuepilot.shared_kernel.errors import PolicyDeniedError
from issuepilot.shared_kernel.ids import new_ulid

_STAGING_PREFIX = ".staging-"


class WorkspaceLayout:
    """Resolves the paths the repository context works with."""

    def __init__(self, root: Path) -> None:
        self._root = root

    @property
    def root(self) -> Path:
        return self._root

    def repository_dir(self, fingerprint: str) -> Path:
        return self._root / "repositories" / fingerprint

    def object_cache(self, fingerprint: str) -> Path:
        return self.repository_dir(fingerprint) / "objects.git"

    def lock_file(self, fingerprint: str) -> Path:
        return self.repository_dir(fingerprint) / "lock"

    def snapshot_dir(self, fingerprint: str) -> Path:
        return self._root / "snapshots" / fingerprint

    def snapshot_path(self, fingerprint: str, sha: str) -> Path:
        return self.snapshot_dir(fingerprint) / sha

    def new_staging_path(self, fingerprint: str) -> Path:
        return self.snapshot_dir(fingerprint) / f"{_STAGING_PREFIX}{new_ulid()}"

    def has_snapshot(self, fingerprint: str, sha: str) -> bool:
        return self.snapshot_path(fingerprint, sha).is_dir()

    def prepare(self, fingerprint: str) -> None:
        self.repository_dir(fingerprint).mkdir(parents=True, exist_ok=True)
        self.snapshot_dir(fingerprint).mkdir(parents=True, exist_ok=True)

    def stale_staging_paths(self, fingerprint: str) -> list[Path]:
        directory = self.snapshot_dir(fingerprint)
        if not directory.is_dir():
            return []
        return [p for p in directory.iterdir() if p.name.startswith(_STAGING_PREFIX)]


@contextmanager
def repository_lock(lock_path: Path, *, blocking: bool = True) -> Iterator[None]:
    """Hold an exclusive inter-process lock for one repository.

    Concurrent ``issuepilot`` runs against the same repository would
    otherwise race on the shared object cache. The lock is advisory and
    released by the OS if the process dies, so a crash cannot wedge the
    cache permanently.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        flags = fcntl.LOCK_EX if blocking else fcntl.LOCK_EX | fcntl.LOCK_NB
        try:
            fcntl.flock(handle, flags)
        except BlockingIOError as exc:
            raise PolicyDeniedError(
                "another issuepilot process is working on this repository",
                remediation="wait for it to finish, or run against a different repository",
            ) from exc
        yield
    finally:
        fcntl.flock(handle, fcntl.LOCK_UN)
        os.close(handle)


def publish_atomically(staging: Path, destination: Path) -> None:
    """Move a completed staging tree into place with one rename.

    If another process published the same snapshot while we worked, theirs
    is equally valid — identical commit, identical content — so we discard
    ours rather than fighting over the destination.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        shutil.rmtree(staging, ignore_errors=True)
        return
    try:
        os.rename(staging, destination)
    except OSError:
        if destination.is_dir():
            shutil.rmtree(staging, ignore_errors=True)
            return
        raise


def make_read_only(root: Path) -> None:
    """Best-effort: strip write bits from a published snapshot.

    Advisory only — it documents intent and catches accidents. It is not a
    security control, since the owner can always restore write permission.
    """
    for current, directories, files in os.walk(root):
        for name in files:
            path = Path(current) / name
            if path.is_symlink():
                continue
            try:
                mode = path.stat().st_mode
                path.chmod(mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)
            except OSError:
                continue
        del directories  # walk order is irrelevant; we touch files only


def remove_snapshot_tree(path: Path) -> None:
    """Delete a snapshot, restoring write permission first."""

    def _force_writable(_func: object, target: str, _exc: object) -> None:
        try:
            Path(target).chmod(0o700)
        except OSError:
            return

    shutil.rmtree(path, onexc=_force_writable)


def resolve_within(root: Path, relative: str) -> Path:
    """Resolve ``relative`` under ``root``, refusing anything that escapes.

    Both sides are fully resolved before comparison, so a symlink pointing
    outside the snapshot is rejected even though its textual path looks
    contained.
    """
    resolved_root = root.resolve(strict=False)
    candidate = (resolved_root / relative).resolve(strict=False)
    if candidate != resolved_root and resolved_root not in candidate.parents:
        raise PolicyDeniedError(
            f"path escapes the repository snapshot: {relative}",
            remediation="the file is a symlink pointing outside the repository and was not read",
        )
    return candidate
