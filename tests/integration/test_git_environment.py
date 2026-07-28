"""git must run in a stable, non-interactive environment.

These are regression tests for defects that only appear on someone else's
machine: a localized git breaks stderr classification, and an interactive
prompt hangs a non-interactive run forever.
"""

from __future__ import annotations

import pytest

from issuepilot.adapters.git.client import run_git

pytestmark = pytest.mark.integration


def test_git_messages_are_locale_pinned_to_english() -> None:
    """Error classification matches English text, so git must speak English
    regardless of the developer's or user's locale."""
    result = run_git(["rev-parse", "--verify", "definitely-not-a-revision"], timeout_seconds=30)
    assert not result.ok
    assert "fatal:" in result.stderr
    # The Spanish translation of this message; present before the locale pin.
    assert "necesit" not in result.stderr.lower()


def test_locale_pin_survives_a_hostile_ambient_locale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LC_ALL", "es_ES.UTF-8")
    monkeypatch.setenv("LANG", "es_ES.UTF-8")
    result = run_git(["rev-parse", "--verify", "definitely-not-a-revision"], timeout_seconds=30)
    assert not result.ok
    assert "necesit" not in result.stderr.lower()


def test_terminal_prompting_is_disabled_by_default() -> None:
    """A run that would otherwise block on a credential prompt must fail fast."""
    result = run_git(
        ["ls-remote", "--end-of-options", "https://127.0.0.1:1/private.git"],
        timeout_seconds=30,
    )
    assert not result.ok
