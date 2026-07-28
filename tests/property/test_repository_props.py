from __future__ import annotations

import string

import pytest
from hypothesis import given
from hypothesis import strategies as st

from issuepilot.repository.domain.manifest import ExclusionReason, FileEligibilityPolicy
from issuepilot.repository.domain.values import (
    LocatorKind,
    RelativeRepoPath,
    RepositoryLocator,
)

POLICY = FileEligibilityPolicy(max_file_bytes=1024)

path_segments = st.text(
    alphabet=string.ascii_letters + string.digits + "-_.", min_size=1, max_size=12
).filter(lambda s: s not in (".", ".."))

repo_paths = st.lists(path_segments, min_size=1, max_size=4).map("/".join)

hosts = st.sampled_from(["github.com", "gitlab.com", "git.internal.example"])
owners = st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=8)
repos = st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=8)


@given(repo_paths, st.integers(min_value=0, max_value=10_000), st.booleans())
def test_policy_is_total_and_deterministic(path: str, size: int, is_binary: bool) -> None:
    """Every path gets a verdict, and the same input always gets the same one."""
    relative = RelativeRepoPath(path)
    first = POLICY.evaluate(relative, size, is_binary=is_binary)
    second = POLICY.evaluate(relative, size, is_binary=is_binary)
    assert first == second
    assert first is None or isinstance(first, ExclusionReason)


@given(repo_paths, st.integers(min_value=1025, max_value=10_000))
def test_oversized_text_files_are_never_eligible(path: str, size: int) -> None:
    assert POLICY.evaluate(RelativeRepoPath(path), size, is_binary=False) is not None


@given(repo_paths, st.integers(min_value=0, max_value=1024))
def test_vendored_paths_are_never_eligible(path: str, size: int) -> None:
    vendored = RelativeRepoPath(f"node_modules/{path}")
    assert POLICY.evaluate(vendored, size, is_binary=False) is not None


@given(hosts, owners, repos)
def test_https_and_ssh_forms_of_one_repo_agree(host: str, owner: str, repo: str) -> None:
    https = RepositoryLocator.parse(f"https://{host}/{owner}/{repo}.git")
    ssh = RepositoryLocator.parse(f"git@{host}:{owner}/{repo}.git")
    assert https.kind is LocatorKind.HTTPS
    assert ssh.kind is LocatorKind.SSH
    assert https.fingerprint() == ssh.fingerprint()


@given(hosts, owners, repos)
def test_fingerprints_are_hex_of_fixed_width(host: str, owner: str, repo: str) -> None:
    value = RepositoryLocator.parse(f"https://{host}/{owner}/{repo}.git").fingerprint()
    assert len(value) == 32
    assert all(c in string.hexdigits for c in value)


@given(st.text(max_size=40))
def test_locator_parsing_never_raises_anything_but_value_error(raw: str) -> None:
    """Hostile input must fail as a typed rejection, not an unexpected crash."""
    try:
        RepositoryLocator.parse(raw)
    except ValueError:
        pass
    except Exception as exc:  # pragma: no cover - this failing is the point
        pytest.fail(f"parse({raw!r}) raised {type(exc).__name__}: {exc}")
