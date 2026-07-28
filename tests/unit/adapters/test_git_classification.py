from __future__ import annotations

import pytest

from issuepilot.adapters.git.client import GitResult
from issuepilot.adapters.git.porcelain import GitErrorCategory, classify_failure


def failure(stderr: str) -> GitResult:
    return GitResult(returncode=128, stdout="", stderr=stderr)


@pytest.mark.parametrize(
    ("stderr", "category"),
    [
        (
            "git@github.com: Permission denied (publickey).\nfatal: Could not read from remote",
            GitErrorCategory.AUTHENTICATION,
        ),
        ("fatal: could not read Username for 'https://gh.com'", GitErrorCategory.AUTHENTICATION),
        ("remote: Support for password authentication was removed.\nfatal: Authentication failed",
         GitErrorCategory.AUTHENTICATION),
        ("Host key verification failed.\nfatal: Could not read from remote repository.",
         GitErrorCategory.HOST_KEY),
        ("fatal: couldn't find remote ref no-such-branch", GitErrorCategory.REF_NOT_FOUND),
        ("fatal: Needed a single revision", GitErrorCategory.REF_NOT_FOUND),
        ("fatal: ambiguous argument 'nope': unknown revision", GitErrorCategory.REF_NOT_FOUND),
        ("remote: Repository not found.\nfatal: repository not found", GitErrorCategory.NOT_FOUND),
        ("fatal: could not resolve host: github.com", GitErrorCategory.NETWORK),
        ("ssh: connect to host github.com port 22: Connection refused", GitErrorCategory.NETWORK),
        ("fatal: the remote end hung up unexpectedly", GitErrorCategory.UNAVAILABLE),
        ("fatal: something nobody has seen before", GitErrorCategory.UNKNOWN),
    ],
)  # fmt: skip
def test_stderr_maps_to_an_actionable_category(stderr: str, category: GitErrorCategory) -> None:
    error = classify_failure(failure(stderr))
    assert error.category is category


def test_host_key_wins_over_permission_denied() -> None:
    """Some platforms print both; the host-key hint is the useful one."""
    stderr = "Host key verification failed.\ngit@host: Permission denied (publickey)."
    assert classify_failure(failure(stderr)).category is GitErrorCategory.HOST_KEY


def test_known_categories_carry_remediation() -> None:
    error = classify_failure(failure("Host key verification failed."))
    assert error.remediation
    assert "known_hosts" in error.remediation


def test_summary_skips_progress_noise() -> None:
    stderr = (
        "remote: Enumerating objects: 42, done.\n"
        "Receiving objects: 100% (42/42), done.\n"
        "fatal: couldn't find remote ref nope\n"
    )
    assert str(classify_failure(failure(stderr))) == "fatal: couldn't find remote ref nope"


def test_summary_survives_empty_stderr() -> None:
    assert str(classify_failure(failure(""))) == "git failed without output"
