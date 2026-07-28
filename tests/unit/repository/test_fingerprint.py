from __future__ import annotations

import pytest

from issuepilot.repository.domain.values import RepositoryLocator


def fingerprint(raw: str, *, allow_local_path: bool = False) -> str:
    return RepositoryLocator.parse(raw, allow_local_path=allow_local_path).fingerprint()


def test_fingerprint_is_stable_and_opaque() -> None:
    value = fingerprint("https://github.com/example/repo.git")
    assert value == fingerprint("https://github.com/example/repo.git")
    assert len(value) == 32
    assert "github" not in value  # the host is not recoverable from the key


@pytest.mark.parametrize(
    "equivalent",
    [
        "https://github.com/example/repo.git",
        "https://github.com/example/repo",
        "https://github.com/example/repo/",
        "ssh://git@github.com/example/repo.git",
        "git@github.com:example/repo.git",
        "GIT@GITHUB.COM:example/repo.GIT",
    ],
)
def test_same_repository_reached_different_ways_shares_a_cache_key(equivalent: str) -> None:
    assert fingerprint(equivalent) == fingerprint("https://github.com/example/repo.git")


@pytest.mark.parametrize(
    "different",
    [
        "https://github.com/example/other.git",
        "https://github.com/other/repo.git",
        "https://gitlab.com/example/repo.git",
    ],
)
def test_different_repositories_get_different_keys(different: str) -> None:
    assert fingerprint(different) != fingerprint("https://github.com/example/repo.git")


def test_port_is_part_of_the_identity() -> None:
    assert fingerprint("https://host.example:8443/team/repo.git") != fingerprint(
        "https://host.example/team/repo.git"
    )


def test_local_paths_fingerprint_by_normalized_path() -> None:
    assert fingerprint("/srv/repo/", allow_local_path=True) == fingerprint(
        "/srv/repo", allow_local_path=True
    )
