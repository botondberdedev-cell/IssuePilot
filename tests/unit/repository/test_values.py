from __future__ import annotations

import pytest

from issuepilot.repository.domain.values import (
    CommitSha,
    LineRange,
    LocatorKind,
    RelativeRepoPath,
    RepositoryLocator,
    RepositoryRef,
)


class TestRepositoryLocator:
    @pytest.mark.parametrize(
        ("raw", "kind"),
        [
            ("https://github.com/example/repo.git", LocatorKind.HTTPS),
            ("https://gitlab.example.com:8443/team/repo.git", LocatorKind.HTTPS),
            ("ssh://git@github.com/example/repo.git", LocatorKind.SSH),
            ("git@github.com:example/repo.git", LocatorKind.SSH),
            ("github.com:example/repo.git", LocatorKind.SSH),
        ],
    )
    def test_accepts_supported_forms(self, raw: str, kind: LocatorKind) -> None:
        locator = RepositoryLocator.parse(raw)
        assert locator.kind is kind
        assert locator.raw == raw

    def test_local_path_requires_opt_in(self) -> None:
        with pytest.raises(ValueError, match="allow-local-path"):
            RepositoryLocator.parse("/Users/dev/repo")
        locator = RepositoryLocator.parse("/Users/dev/repo", allow_local_path=True)
        assert locator.kind is LocatorKind.LOCAL_PATH


class TestRepositoryRef:
    @pytest.mark.parametrize("good", ["main", "v2.4.1", "feature/retry-fix", "a" * 40])
    def test_accepts_reasonable_refs(self, good: str) -> None:
        assert RepositoryRef(good).value == good

    @pytest.mark.parametrize("bad", ["", "  ", "-rf", "a..b", "a//b", "back\\slash", "end."])
    def test_rejects_malformed_refs(self, bad: str) -> None:
        with pytest.raises(ValueError, match="ref"):
            RepositoryRef(bad)


class TestCommitSha:
    def test_accepts_full_lowercase_sha(self) -> None:
        sha = CommitSha("4f2a7c" + "0" * 34)
        assert sha.short == "4f2a7c000000"

    @pytest.mark.parametrize("bad", ["4f2a7c", "G" * 40, "4F2A7C" + "0" * 34, ""])
    def test_rejects_partial_or_malformed(self, bad: str) -> None:
        with pytest.raises(ValueError, match="commit sha"):
            CommitSha(bad)


class TestRelativeRepoPath:
    @pytest.mark.parametrize("good", ["src/app.py", "README.md", "a/b/c.txt"])
    def test_accepts_normalized_relative_paths(self, good: str) -> None:
        assert RelativeRepoPath(good).value == good

    @pytest.mark.parametrize(
        "bad",
        ["", "/abs/path", "~/home", "a/../b", "./a", "a//b", "a/b/", "nul\x00byte", "C:/win"],
    )
    def test_rejects_absolute_and_traversal(self, bad: str) -> None:
        with pytest.raises(ValueError, match="path"):
            RelativeRepoPath(bad)


class TestLineRange:
    def test_single_line_range(self) -> None:
        assert LineRange(5, 5).line_count == 1

    def test_multi_line_count(self) -> None:
        assert LineRange(10, 14).line_count == 5

    @pytest.mark.parametrize(("start", "end"), [(0, 5), (-1, 2), (10, 9)])
    def test_rejects_invalid_bounds(self, start: int, end: int) -> None:
        with pytest.raises(ValueError, match="line range"):
            LineRange(start, end)
