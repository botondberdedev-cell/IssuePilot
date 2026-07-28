"""Contract suite for SourcePort (the repository translator joins in the
bootstrap wiring tests; the fake covers the shape)."""

from __future__ import annotations

import pytest

from issuepilot.knowledge.application.ports import SourceFile, SourcePort
from tests.support.fakes.knowledge import FakeSource

SHA = "a" * 40


@pytest.fixture(params=["fake"])
def source(request: pytest.FixtureRequest) -> SourcePort:
    fake = FakeSource()
    fake.add("src/app.py", "def main():\n    pass\n", "Python")
    fake.add("README.md", "# Title\n", "Markdown")
    return fake


def test_yields_files_with_content_and_language(source: SourcePort) -> None:
    files = list(source.eligible_files(SHA))
    assert len(files) == 2
    assert all(isinstance(f, SourceFile) for f in files)
    assert all(f.text for f in files)


def test_language_is_reported_when_known(source: SourcePort) -> None:
    by_path = {f.path: f for f in source.eligible_files(SHA)}
    assert by_path["src/app.py"].language == "Python"


def test_empty_source_is_allowed() -> None:
    assert list(FakeSource().eligible_files(SHA)) == []
