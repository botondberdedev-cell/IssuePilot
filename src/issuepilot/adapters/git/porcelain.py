"""Git operations expressed as typed functions.

This module knows git: argv construction, output parsing, and the mapping
from git's stderr to an actionable error category. It knows nothing about
IssuePilot's domain — the repository context's infrastructure layer maps
these results onto domain types.

Two safety rules hold throughout:

- User-controlled values (locators, refs) are passed after
  ``--end-of-options`` so a value that looks like a flag cannot become one,
  even though the locator value object already rejects a leading ``-``.
- Output is parsed from NUL-separated formats, so paths containing spaces,
  newlines, or quotes survive intact.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, unique
from pathlib import Path
from typing import Final

from issuepilot.adapters.git.client import GitInvocationError, GitResult, run_git

# git's well-known empty tree; diffing against it makes every path an
# addition, which is what lets one `diff --numstat` classify the whole tree.
EMPTY_TREE_SHA: Final = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

_FULL_SHA_RE: Final = re.compile(r"^[0-9a-f]{40}$")


@unique
class GitErrorCategory(Enum):
    AUTHENTICATION = "authentication"
    HOST_KEY = "host-key"
    NOT_FOUND = "not-found"
    REF_NOT_FOUND = "ref-not-found"
    NETWORK = "network"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class GitError(Exception):
    def __init__(
        self, message: str, category: GitErrorCategory, *, remediation: str | None = None
    ) -> None:
        super().__init__(message)
        self.category = category
        self.remediation = remediation


# Ordered most-specific first: a host-key failure also mentions "Permission
# denied" on some platforms, so it must match before the auth patterns.
_ERROR_PATTERNS: Final[list[tuple[re.Pattern[str], GitErrorCategory, str]]] = [
    (
        re.compile(r"host key verification failed|no matching host key", re.I),
        GitErrorCategory.HOST_KEY,
        "verify the host's fingerprint and add it to ~/.ssh/known_hosts yourself",
    ),
    (
        re.compile(
            r"permission denied \(publickey|could not read username|authentication failed",
            re.I,
        ),
        GitErrorCategory.AUTHENTICATION,
        "ensure your SSH agent holds a key for this host (ssh-add -l), "
        "or that git's credential helper is configured for HTTPS",
    ),
    (
        re.compile(
            r"couldn't find remote ref|unknown revision|pathspec .* did not match"
            # rev-parse --verify's way of saying the revision does not resolve
            r"|needed a single revision|ambiguous argument",
            re.I,
        ),
        GitErrorCategory.REF_NOT_FOUND,
        "check the branch, tag, or commit exists on the remote",
    ),
    (
        re.compile(r"repository not found|does not appear to be a git repository|not found", re.I),
        GitErrorCategory.NOT_FOUND,
        "check the repository URL, and that your account can read it",
    ),
    (
        re.compile(
            r"could not resolve host|connection refused"
            r"|network is unreachable|connection timed out",
            re.I,
        ),
        GitErrorCategory.NETWORK,
        "check network connectivity and any proxy configuration",
    ),
    (
        re.compile(r"early eof|remote end hung up|the remote end hung up unexpectedly", re.I),
        GitErrorCategory.UNAVAILABLE,
        "the remote closed the connection; retry, or reduce --depth",
    ),
]  # fmt: skip


def classify_failure(result: GitResult) -> GitError:
    """Turn a failed git run into a typed, actionable error."""
    text = f"{result.stderr}\n{result.stdout}"
    for pattern, category, remediation in _ERROR_PATTERNS:
        if pattern.search(text):
            return GitError(_summarize(result.stderr), category, remediation=remediation)
    return GitError(_summarize(result.stderr), GitErrorCategory.UNKNOWN)


def _summarize(stderr: str) -> str:
    """First meaningful stderr line; git's progress noise is not an error."""
    for line in stderr.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith(("remote:", "Receiving", "Resolving", "warning:")):
            return stripped
    return stderr.strip().splitlines()[0] if stderr.strip() else "git failed without output"


def _run(args: list[str], *, cwd: Path | None = None, timeout_seconds: float = 300.0) -> GitResult:
    try:
        result = run_git(args, cwd=cwd, timeout_seconds=timeout_seconds)
    except GitInvocationError as exc:
        category = (
            GitErrorCategory.TIMEOUT if "timed out" in str(exc) else GitErrorCategory.UNAVAILABLE
        )
        raise GitError(str(exc), category) from exc
    if not result.ok:
        raise classify_failure(result)
    return result


@dataclass(frozen=True, slots=True)
class TreeEntry:
    path: str
    size_bytes: int
    is_binary: bool


def init_bare_cache(git_dir: Path) -> None:
    """Create (or leave alone) the bare object cache for one repository."""
    if (git_dir / "HEAD").exists():
        return
    git_dir.mkdir(parents=True, exist_ok=True)
    _run(["init", "--bare", "--quiet", str(git_dir)], timeout_seconds=60)


def fetch_ref(
    git_dir: Path,
    locator: str,
    ref: str,
    *,
    depth: int,
    timeout_seconds: float = 600.0,
) -> None:
    """Fetch one ref into the bare cache, storing it as FETCH_HEAD.

    Submodules and LFS content are never fetched here; including them is an
    explicit, separately-implemented opt-in.
    """
    _run(
        [
            "--git-dir",
            str(git_dir),
            "-c",
            "filter.lfs.smudge=",
            "-c",
            "filter.lfs.required=false",
            "fetch",
            "--quiet",
            "--no-tags",
            "--no-recurse-submodules",
            f"--depth={depth}",
            "--end-of-options",
            locator,
            ref,
        ],
        timeout_seconds=timeout_seconds,
    )


def resolve_ref(git_dir: Path, ref: str) -> str:
    """Resolve a ref to its full 40-hex commit SHA."""
    result = _run(
        [
            "--git-dir",
            str(git_dir),
            "rev-parse",
            "--verify",
            "--end-of-options",
            f"{ref}^{{commit}}",
        ],
        timeout_seconds=30,
    )
    sha = result.stdout.strip()
    if not _FULL_SHA_RE.match(sha):
        raise GitError(
            f"git returned an unexpected revision for {ref!r}",
            GitErrorCategory.REF_NOT_FOUND,
        )
    return sha


def remote_head_ref(locator: str, *, timeout_seconds: float = 60.0) -> str:
    """The remote's default branch, as a short name (e.g. ``main``)."""
    result = _run(
        ["ls-remote", "--symref", "--end-of-options", locator, "HEAD"],
        timeout_seconds=timeout_seconds,
    )
    for line in result.stdout.splitlines():
        if line.startswith("ref:"):
            parts = line.split()
            if len(parts) >= 2 and parts[1].startswith("refs/heads/"):
                return parts[1].removeprefix("refs/heads/")
    raise GitError(
        "the remote did not report a default branch",
        GitErrorCategory.REF_NOT_FOUND,
        remediation="pass --ref explicitly",
    )


def list_tree(git_dir: Path, sha: str) -> list[TreeEntry]:
    """Every tracked blob at ``sha`` with its size and binary verdict.

    Binary classification comes from git itself (``diff --numstat`` reports
    ``-`` for binary), so ``.gitattributes`` overrides are respected rather
    than second-guessed with our own content sniffing.
    """
    binary_paths = _binary_paths(git_dir, sha)
    result = _run(
        ["--git-dir", str(git_dir), "ls-tree", "-r", "-l", "-z", "--end-of-options", sha],
        timeout_seconds=120,
    )
    entries: list[TreeEntry] = []
    for record in result.stdout.split("\0"):
        if not record:
            continue
        header, _, path = record.partition("\t")
        if not path:
            continue
        fields = header.split()
        # <mode> <type> <sha> <size>; size is '-' for submodule entries.
        if len(fields) != 4 or fields[1] != "blob" or fields[3] == "-":
            continue
        entries.append(
            TreeEntry(path=path, size_bytes=int(fields[3]), is_binary=path in binary_paths)
        )
    return entries


def _binary_paths(git_dir: Path, sha: str) -> set[str]:
    result = _run(
        [
            "--git-dir",
            str(git_dir),
            "diff",
            "--numstat",
            "-z",
            "--no-renames",
            "--end-of-options",
            EMPTY_TREE_SHA,
            sha,
        ],
        timeout_seconds=120,
    )
    binary: set[str] = set()
    for record in result.stdout.split("\0"):
        if not record:
            continue
        added, _, rest = record.partition("\t")
        deleted, _, path = rest.partition("\t")
        if added == "-" and deleted == "-" and path:
            binary.add(path)
    return binary


def create_worktree(git_dir: Path, sha: str, destination: Path) -> None:
    """Materialize a detached worktree at ``sha``.

    LFS smudging is disabled so pointer files stay as pointers unless the
    user explicitly opted into LFS content.
    """
    _run(
        [
            "--git-dir",
            str(git_dir),
            "-c",
            "filter.lfs.smudge=",
            "-c",
            "filter.lfs.required=false",
            "worktree",
            "add",
            "--detach",
            "--force",
            str(destination),
            sha,
        ],
        timeout_seconds=300,
    )


def prune_worktrees(git_dir: Path) -> None:
    """Drop registrations whose working directories are gone.

    Deliberately *not* ``worktree remove``: that deletes the directory's
    contents, which is the opposite of what publishing a snapshot needs. We
    detach the tree from git first, then prune the dangling registration.
    """
    _run(["--git-dir", str(git_dir), "worktree", "prune"], timeout_seconds=60)
