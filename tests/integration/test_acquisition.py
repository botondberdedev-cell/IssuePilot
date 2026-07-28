"""Acquisition against real git: pinning, reuse, atomicity, locking, offline."""

from __future__ import annotations

import multiprocessing
import time
from pathlib import Path

import pytest

from issuepilot.repository.domain.snapshot import AcquisitionOptions
from issuepilot.repository.domain.values import RepositoryLocator, RepositoryRef
from issuepilot.repository.infrastructure.git_acquirer import GitRepositoryAcquirer
from issuepilot.repository.infrastructure.workspace import (
    WorkspaceLayout,
    repository_lock,
)
from issuepilot.shared_kernel.cancellation import CancellationToken
from issuepilot.shared_kernel.errors import (
    AcquisitionError,
    OperationInterruptedError,
    PolicyDeniedError,
)
from tests.support.fixture_repos import FixtureRepo, add_commit, build_messy_repo, build_simple_repo

pytestmark = pytest.mark.integration

OPTIONS = AcquisitionOptions(history_depth=10)


@pytest.fixture
def source(tmp_path: Path) -> FixtureRepo:
    return build_simple_repo(tmp_path / "source")


@pytest.fixture
def layout(tmp_path: Path) -> WorkspaceLayout:
    return WorkspaceLayout(tmp_path / "workspace")


@pytest.fixture
def acquirer(layout: WorkspaceLayout) -> GitRepositoryAcquirer:
    return GitRepositoryAcquirer(layout)


def locator_for(repo: FixtureRepo) -> RepositoryLocator:
    return RepositoryLocator.parse(repo.locator, allow_local_path=True)


class TestAcquisition:
    def test_pins_the_full_commit_sha(
        self, acquirer: GitRepositoryAcquirer, source: FixtureRepo
    ) -> None:
        result = acquirer.acquire(locator_for(source), RepositoryRef("main"), OPTIONS)
        assert result.commit_sha.value == source.head_sha
        assert not result.reused_cache

    def test_materializes_readable_content(
        self, acquirer: GitRepositoryAcquirer, source: FixtureRepo
    ) -> None:
        result = acquirer.acquire(locator_for(source), RepositoryRef("main"), OPTIONS)
        root = Path(result.root_path)
        assert (root / "src/refunds/webhook.py").is_file()
        assert "handle_retry" in (root / "src/refunds/webhook.py").read_text()

    def test_reports_tracked_files_with_binary_flags(
        self, layout: WorkspaceLayout, tmp_path: Path
    ) -> None:
        messy = build_messy_repo(tmp_path / "messy")
        result = GitRepositoryAcquirer(layout).acquire(
            locator_for(messy), RepositoryRef("main"), OPTIONS
        )
        by_path = {f.path.value: f for f in result.files}
        assert by_path["assets/logo.png"].is_binary
        assert not by_path["src/app.py"].is_binary

    def test_snapshot_is_inert_content_without_git_metadata(
        self, acquirer: GitRepositoryAcquirer, source: FixtureRepo
    ) -> None:
        result = acquirer.acquire(locator_for(source), RepositoryRef("main"), OPTIONS)
        assert not (Path(result.root_path) / ".git").exists()

    def test_published_files_are_read_only(
        self, acquirer: GitRepositoryAcquirer, source: FixtureRepo
    ) -> None:
        result = acquirer.acquire(locator_for(source), RepositoryRef("main"), OPTIONS)
        readme = Path(result.root_path) / "README.md"
        assert not readme.stat().st_mode & 0o222

    def test_unknown_ref_fails_as_acquisition_error(
        self, acquirer: GitRepositoryAcquirer, source: FixtureRepo
    ) -> None:
        with pytest.raises(AcquisitionError) as exc_info:
            acquirer.acquire(locator_for(source), RepositoryRef("no-such-ref"), OPTIONS)
        assert exc_info.value.remediation


class TestCacheReuse:
    def test_second_acquisition_of_the_same_commit_is_reused(
        self, acquirer: GitRepositoryAcquirer, source: FixtureRepo
    ) -> None:
        first = acquirer.acquire(locator_for(source), RepositoryRef("main"), OPTIONS)
        second = acquirer.acquire(locator_for(source), RepositoryRef("main"), OPTIONS)
        assert second.reused_cache
        assert second.root_path == first.root_path

    def test_a_new_commit_gets_its_own_snapshot(
        self, acquirer: GitRepositoryAcquirer, source: FixtureRepo
    ) -> None:
        first = acquirer.acquire(locator_for(source), RepositoryRef("main"), OPTIONS)
        add_commit(source, {"src/added.py": "x = 1\n"}, message="second")
        second = acquirer.acquire(locator_for(source), RepositoryRef("main"), OPTIONS)

        assert second.commit_sha != first.commit_sha
        assert second.root_path != first.root_path
        # The earlier snapshot is untouched: old citations still resolve.
        assert (Path(first.root_path) / "src/refunds/webhook.py").is_file()
        assert not (Path(first.root_path) / "src/added.py").exists()


class TestAtomicPublication:
    def test_no_staging_directories_survive_a_successful_run(
        self, acquirer: GitRepositoryAcquirer, source: FixtureRepo, layout: WorkspaceLayout
    ) -> None:
        acquirer.acquire(locator_for(source), RepositoryRef("main"), OPTIONS)
        fingerprint = locator_for(source).fingerprint()
        assert layout.stale_staging_paths(fingerprint) == []

    def test_cancellation_leaves_no_published_snapshot(
        self, layout: WorkspaceLayout, source: FixtureRepo
    ) -> None:
        token = CancellationToken()
        token.cancel()
        with pytest.raises(OperationInterruptedError):
            GitRepositoryAcquirer(layout, cancellation=token).acquire(
                locator_for(source), RepositoryRef("main"), OPTIONS
            )
        fingerprint = locator_for(source).fingerprint()
        snapshot_dir = layout.snapshot_dir(fingerprint)
        published = list(snapshot_dir.iterdir()) if snapshot_dir.is_dir() else []
        assert published == []


class TestOfflineMode:
    def test_offline_fails_when_nothing_is_cached(
        self, acquirer: GitRepositoryAcquirer, source: FixtureRepo
    ) -> None:
        with pytest.raises(AcquisitionError, match="not available in the local cache"):
            acquirer.acquire(locator_for(source), RepositoryRef("main"), OPTIONS, offline=True)

    def test_offline_reuses_a_previously_fetched_commit(
        self, acquirer: GitRepositoryAcquirer, source: FixtureRepo
    ) -> None:
        online = acquirer.acquire(locator_for(source), RepositoryRef("main"), OPTIONS)
        offline = acquirer.acquire(
            locator_for(source),
            RepositoryRef(online.commit_sha.value),
            OPTIONS,
            offline=True,
        )
        assert offline.commit_sha == online.commit_sha

    def test_offline_never_reaches_the_network(
        self, acquirer: GitRepositoryAcquirer, source: FixtureRepo, tmp_path: Path
    ) -> None:
        """Deleting the source proves no fetch happened on the offline path."""
        online = acquirer.acquire(locator_for(source), RepositoryRef("main"), OPTIONS)
        import shutil

        shutil.rmtree(source.path)
        offline = acquirer.acquire(
            locator_for(source),
            RepositoryRef(online.commit_sha.value),
            OPTIONS,
            offline=True,
        )
        assert offline.commit_sha == online.commit_sha


def _hold_lock(lock_path: str, ready: object, duration: float) -> None:
    with repository_lock(Path(lock_path)):
        ready.set()  # type: ignore[attr-defined]
        time.sleep(duration)


class TestLocking:
    def test_lock_excludes_another_process(self, tmp_path: Path) -> None:
        lock_path = tmp_path / "lock"
        context = multiprocessing.get_context("spawn")
        ready = context.Event()
        holder = context.Process(target=_hold_lock, args=(str(lock_path), ready, 2.0))
        holder.start()
        try:
            assert ready.wait(timeout=10), "helper process never acquired the lock"
            with (
                pytest.raises(PolicyDeniedError, match="another issuepilot process"),
                repository_lock(lock_path, blocking=False),
            ):
                pass
        finally:
            holder.join(timeout=10)

    def test_lock_is_released_after_use(self, tmp_path: Path) -> None:
        lock_path = tmp_path / "lock"
        with repository_lock(lock_path):
            pass
        with repository_lock(lock_path, blocking=False):
            pass  # must not raise
