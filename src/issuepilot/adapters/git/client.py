"""System git invocation.

The only place in the codebase that spawns git. Invariants:

- argv lists, never a shell;
- ``--`` separators are the caller's responsibility at the porcelain layer;
- the environment is inherited so SSH agent and user git config apply;
- output is captured and size-bounded; failures come back typed, not raised
  as raw ``CalledProcessError``.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final

_OUTPUT_LIMIT: Final = 10 * 1024 * 1024  # defensive cap on captured output


@dataclass(frozen=True, slots=True)
class GitResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class GitInvocationError(Exception):
    """git could not be executed at all (missing binary, timeout)."""


def run_git(
    args: list[str],
    *,
    cwd: Path | None = None,
    timeout_seconds: float = 300.0,
    env_overrides: dict[str, str] | None = None,
) -> GitResult:
    """Run ``git <args>`` without a shell and return the typed outcome."""
    env = dict(os.environ)
    # Never allow interactive credential or passphrase prompts from a CLI run.
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    if env_overrides:
        env.update(env_overrides)
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=cwd,
            env=env,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError as exc:
        raise GitInvocationError("git executable not found on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitInvocationError(f"git timed out after {timeout_seconds:.0f}s") from exc
    return GitResult(
        returncode=completed.returncode,
        stdout=completed.stdout[:_OUTPUT_LIMIT].decode("utf-8", errors="replace"),
        stderr=completed.stderr[:_OUTPUT_LIMIT].decode("utf-8", errors="replace"),
    )


def git_version() -> str | None:
    """Installed git version string, or None when git is unavailable."""
    try:
        result = run_git(["--version"], timeout_seconds=10.0)
    except GitInvocationError:
        return None
    return result.stdout.strip() if result.ok else None
