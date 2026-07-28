"""The acquisition use case, driven entirely through fakes — no git."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from issuepilot.repository.application.ports import TrackedFile
from issuepilot.repository.application.use_cases.acquire_snapshot import (
    AcquireSnapshot,
    AcquireSnapshotCommand,
)
from issuepilot.repository.domain.events import (
    RepositoryAcquisitionFailed,
    RepositorySnapshotCreated,
)
from issuepilot.repository.domain.limits import SizeBudget
from issuepilot.repository.domain.manifest import ExclusionReason, FileEligibilityPolicy
from issuepilot.repository.domain.snapshot import AcquisitionOptions, SnapshotState
from issuepilot.repository.domain.values import RelativeRepoPath, RepositoryLocator, RepositoryRef
from issuepilot.shared_kernel.clock import FixedClock
from issuepilot.shared_kernel.errors import AcquisitionError, PolicyDeniedError
from issuepilot.shared_kernel.ids import UlidGenerator
from tests.support.fakes.eventbus import RecordingEventBus
from tests.support.fakes.repository import FakeRepositoryAcquirer, InMemorySnapshotStore

SHA = "a" * 40
LOCATOR = RepositoryLocator.parse("https://github.com/example/repo.git")


def tracked(path: str, size: int = 100, *, binary: bool = False) -> TrackedFile:
    return TrackedFile(path=RelativeRepoPath(path), size_bytes=size, is_binary=binary)


def build(
    files: list[TrackedFile] | None = None,
    *,
    max_file_bytes: int = 1024,
    max_total_bytes: int = 10_000_000,
) -> tuple[AcquireSnapshot, InMemorySnapshotStore, RecordingEventBus, FakeRepositoryAcquirer]:
    acquirer = FakeRepositoryAcquirer()
    acquirer.seed("main", commit_sha=SHA, files=files or [tracked("src/app.py")])
    store = InMemorySnapshotStore()
    bus = RecordingEventBus()
    use_case = AcquireSnapshot(
        acquirer=acquirer,
        store=store,
        eligibility=FileEligibilityPolicy(max_file_bytes=max_file_bytes),
        size_budget=SizeBudget(max_total_bytes=max_total_bytes),
        ids=UlidGenerator(),
        clock=FixedClock(datetime(2026, 7, 28, tzinfo=UTC)),
        bus=bus,
    )
    return use_case, store, bus, acquirer


def command(**overrides: object) -> AcquireSnapshotCommand:
    defaults: dict[str, object] = {
        "locator": LOCATOR,
        "ref": RepositoryRef("main"),
        "options": AcquisitionOptions(history_depth=10),
    }
    return AcquireSnapshotCommand(**(defaults | overrides))  # type: ignore[arg-type]


class TestHappyPath:
    def test_produces_a_ready_pinned_snapshot(self) -> None:
        use_case, _, _, _ = build()
        snapshot = use_case.execute(command())
        assert snapshot.state is SnapshotState.READY
        assert snapshot.pinned_sha().value == SHA

    def test_persists_the_record(self) -> None:
        use_case, store, _, _ = build()
        snapshot = use_case.execute(command())
        assert store.get(snapshot.snapshot_id) is not None

    def test_publishes_a_created_event(self) -> None:
        use_case, _, bus, _ = build()
        use_case.execute(command())
        (event,) = bus.published
        assert isinstance(event, RepositorySnapshotCreated)
        assert event.commit_sha == SHA


class TestManifestConstruction:
    def test_splits_files_by_eligibility_with_reasons(self) -> None:
        use_case, _, _, _ = build(
            [
                tracked("src/app.py"),
                tracked("README.md"),
                tracked(".env"),
                tracked("assets/logo.png", binary=True),
                tracked("src/huge.py", size=99_999),
            ]
        )
        manifest = use_case.execute(command()).manifest
        assert manifest is not None
        assert {e.path.value for e in manifest.included} == {"src/app.py", "README.md"}
        by_path = {e.path.value: e.reason for e in manifest.excluded}
        assert by_path[".env"] is ExclusionReason.SECRET_LIKE
        assert by_path["assets/logo.png"] is ExclusionReason.MEDIA_OR_ARCHIVE
        assert by_path["src/huge.py"] is ExclusionReason.TOO_LARGE

    def test_detects_languages_for_included_files(self) -> None:
        use_case, _, _, _ = build([tracked("src/app.py"), tracked("README.md")])
        manifest = use_case.execute(command()).manifest
        assert manifest is not None
        assert manifest.language_distribution() == {"Python": 1, "Markdown": 1}

    def test_manifest_is_bound_to_the_pinned_commit(self) -> None:
        use_case, _, _, _ = build()
        snapshot = use_case.execute(command())
        assert snapshot.manifest is not None
        assert snapshot.manifest.commit_sha == snapshot.pinned_sha()


class TestRefResolution:
    def test_absent_ref_falls_back_to_the_remote_default(self) -> None:
        use_case, _, _, acquirer = build()
        snapshot = use_case.execute(command(ref=None))
        assert snapshot.requested_ref.value == "main"
        assert acquirer.acquired[-1][1] == "main"

    def test_offline_flag_reaches_the_acquirer(self) -> None:
        use_case, _, _, acquirer = build()
        use_case.execute(command(offline=True))
        assert acquirer.acquired[-1][2] is True


class TestFailure:
    def test_acquisition_failure_publishes_an_event_and_propagates(self) -> None:
        use_case, _, bus, _ = build()
        with pytest.raises(AcquisitionError):
            use_case.execute(command(ref=RepositoryRef("missing")))

        (event,) = bus.published
        assert isinstance(event, RepositoryAcquisitionFailed)
        assert event.reason_category == "acquisition"

    def test_failed_acquisition_persists_nothing(self) -> None:
        use_case, store, _, _ = build()
        with pytest.raises(AcquisitionError):
            use_case.execute(command(ref=RepositoryRef("missing")))
        assert list(store.list_recent()) == []


class TestSizeBudget:
    def test_a_repository_over_the_total_budget_is_denied(self) -> None:
        use_case, _, _, _ = build(
            [tracked("src/a.py", 600), tracked("src/b.py", 600)],
            max_total_bytes=1000,
        )
        with pytest.raises(PolicyDeniedError, match="size budget"):
            use_case.execute(command())

    def test_a_repository_within_the_budget_succeeds(self) -> None:
        use_case, _, _, _ = build(
            [tracked("src/a.py", 400), tracked("src/b.py", 400)],
            max_total_bytes=1000,
        )
        assert use_case.execute(command()).is_ready

    def test_excluded_files_do_not_count_against_the_budget(self) -> None:
        """Only analyzable bytes matter; a huge binary we never read is free."""
        use_case, _, _, _ = build(
            [tracked("src/a.py", 400), tracked("assets/logo.png", 10_000_000, binary=True)],
            max_total_bytes=1000,
        )
        assert use_case.execute(command()).is_ready
