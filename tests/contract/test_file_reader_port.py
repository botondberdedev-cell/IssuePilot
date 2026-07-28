"""Contract suite for FileReaderPort."""

from __future__ import annotations

import pytest

from issuepilot.investigation.application.ports import FileReaderPort
from tests.support.fakes.investigation import FakeFileReader

CONTENT = "alpha\nbravo\ncharlie\ndelta\n"


@pytest.fixture(params=["fake"])
def reader(request: pytest.FixtureRequest) -> FileReaderPort:
    return FakeFileReader({"src/app.py": CONTENT})


def test_reads_the_requested_range(reader: FileReaderPort) -> None:
    assert reader.read("src/app.py", 2, 3) == "bravo\ncharlie\n"


def test_range_beyond_the_end_returns_what_exists(reader: FileReaderPort) -> None:
    assert reader.read("src/app.py", 4, 99) == "delta\n"


def test_missing_file_raises(reader: FileReaderPort) -> None:
    with pytest.raises(FileNotFoundError):
        reader.read("src/missing.py", 1, 2)
