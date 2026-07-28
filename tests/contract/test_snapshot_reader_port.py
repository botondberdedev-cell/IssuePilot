"""Contract suite for SnapshotReaderPort.

Both implementations are exercised through the same assertions, including
the confinement rule: an escaping path is refused by ``read_slice`` and
reported absent by ``contains`` — never silently served.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from issuepilot.repository.application.ports import SnapshotReaderPort
from issuepilot.repository.domain.values import LineRange, RelativeRepoPath
from issuepilot.repository.infrastructure.snapshot_reader import SnapshotReader
from issuepilot.shared_kernel.errors import PolicyDeniedError
from tests.support.fakes.repository import FakeSnapshotReader

CONTENT = "alpha\nbravo\ncharlie\n"


@pytest.fixture(
    params=[
        pytest.param("fake", id="fake"),
        pytest.param("real", id="real", marks=pytest.mark.integration),
    ]
)
def reader_and_root(
    request: pytest.FixtureRequest, tmp_path: Path
) -> Iterator[tuple[SnapshotReaderPort, str]]:
    if request.param == "fake":
        fake = FakeSnapshotReader()
        fake.add_file("/root", "src/app.py", CONTENT)
        fake.add_escaping_path("/root", "escape.txt")
        yield fake, "/root"
        return

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("SECRET\n", encoding="utf-8")
    root = tmp_path / "snapshot"
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.py").write_text(CONTENT, encoding="utf-8")
    (root / "escape.txt").symlink_to(outside / "secret.txt")
    yield SnapshotReader(), str(root)


def test_contains_finds_present_file(
    reader_and_root: tuple[SnapshotReaderPort, str],
) -> None:
    reader, root = reader_and_root
    assert reader.contains(root, RelativeRepoPath("src/app.py"))


def test_contains_is_false_for_absent_file(
    reader_and_root: tuple[SnapshotReaderPort, str],
) -> None:
    reader, root = reader_and_root
    assert not reader.contains(root, RelativeRepoPath("src/missing.py"))


def test_contains_is_false_for_escaping_path(
    reader_and_root: tuple[SnapshotReaderPort, str],
) -> None:
    reader, root = reader_and_root
    assert not reader.contains(root, RelativeRepoPath("escape.txt"))


def test_line_count(reader_and_root: tuple[SnapshotReaderPort, str]) -> None:
    reader, root = reader_and_root
    assert reader.line_count(root, RelativeRepoPath("src/app.py")) == 3


def test_read_slice_returns_requested_lines(
    reader_and_root: tuple[SnapshotReaderPort, str],
) -> None:
    reader, root = reader_and_root
    assert reader.read_slice(root, RelativeRepoPath("src/app.py"), LineRange(2, 3)) == (
        "bravo\ncharlie\n"
    )


def test_read_slice_clamps_to_end_of_file(
    reader_and_root: tuple[SnapshotReaderPort, str],
) -> None:
    reader, root = reader_and_root
    assert reader.read_slice(root, RelativeRepoPath("src/app.py"), LineRange(3, 99)) == (
        "charlie\n"
    )


def test_read_slice_refuses_escaping_path(
    reader_and_root: tuple[SnapshotReaderPort, str],
) -> None:
    reader, root = reader_and_root
    with pytest.raises(PolicyDeniedError, match="escapes"):
        reader.read_slice(root, RelativeRepoPath("escape.txt"), LineRange(1, 1))


def test_missing_file_raises_not_found(
    reader_and_root: tuple[SnapshotReaderPort, str],
) -> None:
    reader, root = reader_and_root
    with pytest.raises(FileNotFoundError):
        reader.read_slice(root, RelativeRepoPath("src/missing.py"), LineRange(1, 1))
