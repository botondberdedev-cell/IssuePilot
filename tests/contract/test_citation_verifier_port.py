"""Contract suite for CitationVerifierPort."""

from __future__ import annotations

import pytest

from issuepilot.investigation.application.ports import CitationVerifierPort
from tests.support.fakes.investigation import FakeCitationVerifier

SHA = "d" * 40


@pytest.fixture(params=["fake"])
def verifier(request: pytest.FixtureRequest) -> CitationVerifierPort:
    fake = FakeCitationVerifier()
    fake.allow("src/app.py", 10, 20, SHA)
    return fake


def test_known_citation_verifies(verifier: CitationVerifierPort) -> None:
    assert verifier.verify("src/app.py", 10, 20, SHA)


def test_unknown_path_fails(verifier: CitationVerifierPort) -> None:
    assert not verifier.verify("src/other.py", 10, 20, SHA)


def test_wrong_range_fails(verifier: CitationVerifierPort) -> None:
    assert not verifier.verify("src/app.py", 10, 21, SHA)


def test_wrong_snapshot_fails(verifier: CitationVerifierPort) -> None:
    assert not verifier.verify("src/app.py", 10, 20, "e" * 40)
