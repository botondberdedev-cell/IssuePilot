"""Build small, real git repositories on demand for integration tests.

Repositories are created at runtime into ``tmp_path`` rather than checked in,
so the suite never carries nested ``.git`` directories. Every git invocation
runs with ``GIT_CONFIG_GLOBAL``/``GIT_CONFIG_SYSTEM`` pointed at nowhere, so
a developer's own git configuration (signing keys, hooks, default branch,
autocrlf) cannot change what these tests see.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from issuepilot.adapters.git.client import run_git

_ISOLATED_ENV = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
    "GIT_AUTHOR_NAME": "IssuePilot Fixture",
    "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
    "GIT_COMMITTER_NAME": "IssuePilot Fixture",
    "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
    # Deterministic timestamps keep commit SHAs stable across runs.
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+00:00",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+00:00",
}


@dataclass(frozen=True, slots=True)
class FixtureRepo:
    path: Path
    head_sha: str
    branch: str

    @property
    def locator(self) -> str:
        """A local path usable as a git remote."""
        return str(self.path)


def git(args: list[str], cwd: Path) -> str:
    result = run_git(args, cwd=cwd, timeout_seconds=60, env_overrides=_ISOLATED_ENV)
    if not result.ok:
        raise AssertionError(f"fixture git {args} failed: {result.stderr}")
    return result.stdout


def build_repo(
    root: Path,
    files: Mapping[str, str | bytes],
    *,
    branch: str = "main",
    message: str = "initial commit",
    symlinks: Mapping[str, str] | None = None,
) -> FixtureRepo:
    """Create a repository containing ``files`` in a single commit.

    ``symlinks`` maps link path to target, and is used by the security suite
    to build links that escape the repository root.
    """
    root.mkdir(parents=True, exist_ok=True)
    git(["init", "--quiet", "-b", branch, "."], cwd=root)

    for relative, content in files.items():
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            destination.write_bytes(content)
        else:
            destination.write_text(content, encoding="utf-8")

    for link_path, target in (symlinks or {}).items():
        link = root / link_path
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(target)

    git(["add", "--all"], cwd=root)
    git(["commit", "--quiet", "-m", message], cwd=root)
    head = git(["rev-parse", "HEAD"], cwd=root).strip()
    return FixtureRepo(path=root, head_sha=head, branch=branch)


def add_commit(repo: FixtureRepo, files: Mapping[str, str], *, message: str) -> FixtureRepo:
    """Add a second (or later) commit, returning the updated fixture."""
    for relative, content in files.items():
        destination = repo.path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
    git(["add", "--all"], cwd=repo.path)
    git(["commit", "--quiet", "-m", message], cwd=repo.path)
    head = git(["rev-parse", "HEAD"], cwd=repo.path).strip()
    return FixtureRepo(path=repo.path, head_sha=head, branch=repo.branch)


def tag(repo: FixtureRepo, name: str) -> None:
    git(["tag", name], cwd=repo.path)


# ── Named fixtures used across the suite ────────────────────────────────────

SIMPLE_FILES: Mapping[str, str | bytes] = {
    "README.md": "# Payments service\n\nHandles refunds and webhooks.\n",
    "src/refunds/webhook.py": (
        "def handle_retry(event):\n"
        "    if is_duplicate(event):\n"
        "        return  # bug: returns before the state transition commits\n"
        "    transition(event)\n"
    ),
    "src/refunds/state.py": "def transition(event):\n    event.state = 'settled'\n",
    "tests/test_refunds.py": "def test_retry():\n    assert True\n",
    "pyproject.toml": '[project]\nname = "payments"\n',
}


def build_simple_repo(root: Path) -> FixtureRepo:
    """A small, well-formed Python repository with one plausible bug."""
    return build_repo(root, SIMPLE_FILES)


def build_messy_repo(root: Path) -> FixtureRepo:
    """Exercises every exclusion reason: binary, media, vendored, build
    output, minified, and secret-like files alongside real source."""
    return build_repo(
        root,
        {
            "src/app.py": "def main():\n    return 0\n",
            "README.md": "# Messy\n",
            ".env": "API_KEY=super-secret-value\n",
            "certs/server.pem": (
                "-----BEGIN PRIVATE KEY-----\nZmFrZQ==\n-----END PRIVATE KEY-----\n"
            ),
            "assets/logo.png": b"\x89PNG\r\n\x1a\n\x00\x00\x00fake",
            "data/blob.dat": b"\x00\x01\x02\x03binary\x00content",
            "node_modules/left-pad/index.js": "module.exports = () => {};\n",
            "build/bundle.js": "console.log('generated');\n",
            "static/app.min.js": "!function(){}();\n",
        },
    )
