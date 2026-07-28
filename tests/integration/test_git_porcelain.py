"""Porcelain against real git processes and real fixture repositories."""

from __future__ import annotations

from pathlib import Path

import pytest

from issuepilot.adapters.git.porcelain import (
    GitError,
    GitErrorCategory,
    create_worktree,
    fetch_ref,
    init_bare_cache,
    list_tree,
    remote_head_ref,
    resolve_ref,
)
from tests.support.fixture_repos import (
    FixtureRepo,
    add_commit,
    build_messy_repo,
    build_simple_repo,
    tag,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def source_repo(tmp_path: Path) -> FixtureRepo:
    return build_simple_repo(tmp_path / "source")


@pytest.fixture
def cache(tmp_path: Path) -> Path:
    git_dir = tmp_path / "cache.git"
    init_bare_cache(git_dir)
    return git_dir


def fetch_and_resolve(cache: Path, repo: FixtureRepo, ref: str | None = None) -> str:
    fetch_ref(cache, repo.locator, ref or repo.branch, depth=10)
    return resolve_ref(cache, "FETCH_HEAD")


class TestFetchAndResolve:
    def test_fetch_then_resolve_yields_the_full_head_sha(
        self, cache: Path, source_repo: FixtureRepo
    ) -> None:
        assert fetch_and_resolve(cache, source_repo) == source_repo.head_sha

    def test_resolving_a_tag_pins_its_commit(self, cache: Path, source_repo: FixtureRepo) -> None:
        tag(source_repo, "v1.0.0")
        assert fetch_and_resolve(cache, source_repo, "v1.0.0") == source_repo.head_sha

    def test_ref_selects_the_commit_not_just_the_tip(
        self, cache: Path, source_repo: FixtureRepo
    ) -> None:
        first_sha = source_repo.head_sha
        tag(source_repo, "v1.0.0")
        updated = add_commit(source_repo, {"src/new.py": "x = 1\n"}, message="second")
        assert updated.head_sha != first_sha
        assert fetch_and_resolve(cache, source_repo, "v1.0.0") == first_sha

    def test_init_bare_cache_is_idempotent(self, tmp_path: Path) -> None:
        git_dir = tmp_path / "twice.git"
        init_bare_cache(git_dir)
        init_bare_cache(git_dir)
        assert (git_dir / "HEAD").exists()

    def test_remote_head_ref_reports_the_default_branch(self, source_repo: FixtureRepo) -> None:
        assert remote_head_ref(source_repo.locator) == "main"


class TestErrorClassification:
    def test_missing_ref_is_categorized(self, cache: Path, source_repo: FixtureRepo) -> None:
        with pytest.raises(GitError) as exc_info:
            fetch_ref(cache, source_repo.locator, "no-such-branch", depth=1)
        assert exc_info.value.category is GitErrorCategory.REF_NOT_FOUND
        assert exc_info.value.remediation

    def test_missing_repository_is_categorized(self, cache: Path, tmp_path: Path) -> None:
        with pytest.raises(GitError) as exc_info:
            fetch_ref(cache, str(tmp_path / "absent"), "main", depth=1)
        assert exc_info.value.category in (
            GitErrorCategory.NOT_FOUND,
            GitErrorCategory.REF_NOT_FOUND,
        )

    def test_resolving_an_unknown_revision_raises(self, cache: Path) -> None:
        with pytest.raises(GitError) as exc_info:
            resolve_ref(cache, "deadbeef")
        assert exc_info.value.category is GitErrorCategory.REF_NOT_FOUND


class TestListTree:
    def test_lists_tracked_files_with_sizes(self, cache: Path, source_repo: FixtureRepo) -> None:
        sha = fetch_and_resolve(cache, source_repo)
        entries = {e.path: e for e in list_tree(cache, sha)}
        assert set(entries) == {
            "README.md",
            "src/refunds/webhook.py",
            "src/refunds/state.py",
            "tests/test_refunds.py",
            "pyproject.toml",
        }
        assert entries["README.md"].size_bytes > 0
        assert not entries["README.md"].is_binary

    def test_binary_files_are_flagged_by_git(self, cache: Path, tmp_path: Path) -> None:
        messy = build_messy_repo(tmp_path / "messy")
        sha = fetch_and_resolve(cache, messy)
        entries = {e.path: e for e in list_tree(cache, sha)}
        assert entries["assets/logo.png"].is_binary
        assert entries["data/blob.dat"].is_binary
        assert not entries["src/app.py"].is_binary

    def test_paths_with_spaces_survive_parsing(self, cache: Path, tmp_path: Path) -> None:
        from tests.support.fixture_repos import build_repo

        repo = build_repo(
            tmp_path / "spaced",
            {"docs/design notes.md": "# Notes\n", "src/a b/c.py": "x = 1\n"},
        )
        sha = fetch_and_resolve(cache, repo)
        paths = {e.path for e in list_tree(cache, sha)}
        assert "docs/design notes.md" in paths
        assert "src/a b/c.py" in paths

    def test_sizes_match_content_length(self, cache: Path, tmp_path: Path) -> None:
        from tests.support.fixture_repos import build_repo

        content = "abcdefghij\n"
        repo = build_repo(tmp_path / "sized", {"f.txt": content})
        sha = fetch_and_resolve(cache, repo)
        (entry,) = [e for e in list_tree(cache, sha) if e.path == "f.txt"]
        assert entry.size_bytes == len(content.encode("utf-8"))


class TestWorktree:
    def test_worktree_materializes_the_pinned_commit(
        self, cache: Path, source_repo: FixtureRepo, tmp_path: Path
    ) -> None:
        sha = fetch_and_resolve(cache, source_repo)
        destination = tmp_path / "snapshot"
        create_worktree(cache, sha, destination)

        assert (destination / "README.md").is_file()
        assert "handle_retry" in (destination / "src/refunds/webhook.py").read_text()

    def test_worktree_content_matches_its_commit_not_later_ones(
        self, cache: Path, source_repo: FixtureRepo, tmp_path: Path
    ) -> None:
        first_sha = fetch_and_resolve(cache, source_repo)
        add_commit(source_repo, {"src/added_later.py": "later = True\n"}, message="later")

        destination = tmp_path / "pinned"
        create_worktree(cache, first_sha, destination)
        assert not (destination / "src/added_later.py").exists()
