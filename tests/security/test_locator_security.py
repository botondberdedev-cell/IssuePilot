"""The locator injection matrix: every rejection here is a threat-model line."""

from __future__ import annotations

import pytest

from issuepilot.repository.domain.values import RepositoryLocator

pytestmark = pytest.mark.security


@pytest.mark.parametrize(
    "hostile",
    [
        "-upload-pack=/bin/evil",
        "--upload-pack=touch /tmp/pwned",
        "git://example.com/repo.git",
        "ftp://example.com/repo.git",
        "ftps://example.com/repo.git",
        "ext::sh -c 'curl evil'",
        "EXT::sh -c whoami",
        "file:///etc/passwd",
        "http://example.com/repo.git",
        "https://user:hunter2@github.com/x/y.git",
        "https://token@github.com/x/y.git",
        "https://github.com/x/y.git\x00",
        "ssh://host/repo\x1b[2J",
        "",
        "   ",
        "relative/local/path",
    ],
)
def test_hostile_locators_are_rejected(hostile: str) -> None:
    with pytest.raises(ValueError):  # noqa: PT011 - the matrix spans many messages
        RepositoryLocator.parse(hostile)


def test_local_paths_rejected_even_with_leading_dash_and_opt_in() -> None:
    with pytest.raises(ValueError, match="'-'"):
        RepositoryLocator.parse("-/etc", allow_local_path=True)


def test_scp_like_cannot_smuggle_a_scheme() -> None:
    # host:path where "path" starts // would be a URL in disguise
    with pytest.raises(ValueError):  # noqa: PT011
        RepositoryLocator.parse("example.com://not-a-repo")
