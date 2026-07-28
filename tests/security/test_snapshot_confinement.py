"""Repository content is untrusted: no read may leave the snapshot root.

A repository can contain symlinks pointing anywhere. Without confinement a
crafted repository could make the tool read — and then *cite*, lending it
false authority — arbitrary files from the user's machine.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from issuepilot.repository.domain.values import LineRange, RelativeRepoPath
from issuepilot.repository.infrastructure.snapshot_reader import SnapshotReader
from issuepilot.repository.infrastructure.workspace import resolve_within
from issuepilot.shared_kernel.errors import PolicyDeniedError

pytestmark = pytest.mark.security


@pytest.fixture
def snapshot(tmp_path: Path) -> Path:
    """A snapshot containing an escaping symlink and a secret just outside."""
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("SECRET MATERIAL\n", encoding="utf-8")

    root = tmp_path / "snapshot"
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.py").write_text("line one\nline two\nline three\n", encoding="utf-8")

    (root / "escape.txt").symlink_to(outside / "secret.txt")
    (root / "escape_dir").symlink_to(outside)
    (root / "self_ref.txt").symlink_to(root / "src" / "app.py")
    (root / "broken.txt").symlink_to(root / "does-not-exist")
    return root


class TestResolveWithin:
    def test_ordinary_path_resolves(self, snapshot: Path) -> None:
        assert resolve_within(snapshot, "src/app.py").is_file()

    def test_symlink_to_outside_file_is_refused(self, snapshot: Path) -> None:
        with pytest.raises(PolicyDeniedError, match="escapes the repository snapshot"):
            resolve_within(snapshot, "escape.txt")

    def test_path_through_escaping_directory_symlink_is_refused(self, snapshot: Path) -> None:
        with pytest.raises(PolicyDeniedError, match="escapes"):
            resolve_within(snapshot, "escape_dir/secret.txt")

    def test_symlink_staying_inside_is_allowed(self, snapshot: Path) -> None:
        assert resolve_within(snapshot, "self_ref.txt").is_file()

    def test_traversal_via_dotdot_is_refused(self, snapshot: Path) -> None:
        with pytest.raises(PolicyDeniedError, match="escapes"):
            resolve_within(snapshot, "../outside/secret.txt")

    def test_absolute_path_is_refused(self, snapshot: Path) -> None:
        with pytest.raises(PolicyDeniedError, match="escapes"):
            resolve_within(snapshot, "/etc/passwd")


class TestSnapshotReaderConfinement:
    def test_reader_refuses_escaping_symlink(self, snapshot: Path) -> None:
        reader = SnapshotReader()
        with pytest.raises(PolicyDeniedError):
            reader.read_slice(str(snapshot), RelativeRepoPath("escape.txt"), LineRange(1, 1))

    def test_contains_reports_false_for_escapes_without_raising(self, snapshot: Path) -> None:
        """Existence checks must not become an oracle for files outside."""
        reader = SnapshotReader()
        assert not reader.contains(str(snapshot), RelativeRepoPath("escape.txt"))
        assert reader.contains(str(snapshot), RelativeRepoPath("src/app.py"))

    def test_broken_symlink_is_not_readable(self, snapshot: Path) -> None:
        reader = SnapshotReader()
        assert not reader.contains(str(snapshot), RelativeRepoPath("broken.txt"))

    def test_secret_content_never_surfaces(self, snapshot: Path) -> None:
        reader = SnapshotReader()
        for candidate in ("escape.txt", "escape_dir/secret.txt"):
            try:
                text = reader.read_slice(
                    str(snapshot), RelativeRepoPath(candidate), LineRange(1, 10)
                )
            except PolicyDeniedError:
                continue
            pytest.fail(f"{candidate} leaked content: {text!r}")


class TestBoundedReads:
    def test_reads_only_the_requested_range(self, snapshot: Path) -> None:
        reader = SnapshotReader()
        text = reader.read_slice(str(snapshot), RelativeRepoPath("src/app.py"), LineRange(2, 2))
        assert text == "line two\n"

    def test_range_beyond_end_returns_what_exists(self, snapshot: Path) -> None:
        reader = SnapshotReader()
        text = reader.read_slice(str(snapshot), RelativeRepoPath("src/app.py"), LineRange(3, 99))
        assert text == "line three\n"

    def test_line_count_is_reported(self, snapshot: Path) -> None:
        assert SnapshotReader().line_count(str(snapshot), RelativeRepoPath("src/app.py")) == 3
