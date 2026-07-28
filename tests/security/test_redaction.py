from __future__ import annotations

import json
import logging
from io import StringIO

import pytest

from issuepilot.adapters.telemetry.logging import (
    REDACTED,
    JsonLinesFormatter,
    RedactionFilter,
    redact,
)

pytestmark = pytest.mark.security


@pytest.mark.parametrize(
    ("text", "must_not_contain"),
    [
        ("cloning https://alice:hunter2@github.com/x/y.git", "hunter2"),
        ("token ghp_abcdefghijklmnopqrstuvwx0123456789", "ghp_abcdefghijklmnopqrstuvwx"),
        ("token github_pat_11ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", "github_pat_11ABCDE"),
        ("key AKIAIOSFODNN7EXAMPLE in env", "AKIAIOSFODNN7EXAMPLE"),
        ("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload", "eyJhbGciOiJIUzI1NiJ9"),
        ("password=sup3rs3cret!", "sup3rs3cret"),
        ("api_key: sk-abc123def456", "sk-abc123def456"),
        (
            "-----BEGIN OPENSSH PRIVATE KEY-----\n"
            "b3BlbnNzaC1rZXk=\n"
            "-----END OPENSSH PRIVATE KEY-----",
            "b3BlbnNzaC1rZXk=",
        ),
    ],
)
def test_redact_removes_secret_material(text: str, must_not_contain: str) -> None:
    result = redact(text)
    assert must_not_contain not in result
    assert REDACTED in result or "REDACTED" in result


def test_redact_preserves_innocent_text() -> None:
    text = "resolved ref main to 4f2a7c1 in 120ms"
    assert redact(text) == text


def test_redact_keeps_host_visible_in_authenticated_urls() -> None:
    result = redact("fetching https://alice:hunter2@github.com/x/y.git")
    assert "github.com/x/y.git" in result
    assert "hunter2" not in result


def test_logging_pipeline_redacts_and_emits_json_lines() -> None:
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(RedactionFilter())
    handler.setFormatter(JsonLinesFormatter())
    logger = logging.Logger("test-isolated")
    logger.addHandler(handler)

    logger.info("auth failed for https://bob:t0ps3cret@example.com/repo.git")

    line = stream.getvalue().strip()
    entry = json.loads(line)
    assert entry["level"] == "INFO"
    assert "t0ps3cret" not in line
    assert "example.com" in entry["message"]
