"""Contract suite for RunStorePort: fake and SQLite."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from issuepilot.adapters.sqlite.connection import connect
from issuepilot.adapters.sqlite.migrator import migrate
from issuepilot.investigation.application.dto import FindingDTO, ReportDTO
from issuepilot.investigation.application.ports import RunStorePort
from issuepilot.investigation.infrastructure.run_repo import SqliteRunStore
from issuepilot.shared_kernel.ids import RunId, new_ulid
from tests.support.fakes.investigation import InMemoryRunStore


@pytest.fixture(
    params=[
        pytest.param("fake", id="fake"),
        pytest.param("sqlite", id="real", marks=pytest.mark.integration),
    ]
)
def store(request: pytest.FixtureRequest) -> Iterator[RunStorePort]:
    if request.param == "fake":
        yield InMemoryRunStore()
        return
    connection = connect(":memory:")
    try:
        migrate(connection)
        yield SqliteRunStore(connection)
    finally:
        connection.close()


def report(run_id: str, *, speculative: bool = False) -> ReportDTO:
    return ReportDTO(
        report_id=new_ulid(),
        run_id=run_id,
        commit_sha="f" * 40,
        issue_summary="refunds stuck in pending",
        completeness="complete",
        findings=(
            FindingDTO(
                claim="the retry path drops the state transition",
                confidence=0.7,
                citations=("src/refunds/webhook.py:84-121 @ ffffffffffff",),
                speculative=speculative,
            ),
        ),
        missing_information=("no logs were available",),
    )


def test_save_load_roundtrip(store: RunStorePort) -> None:
    run_id = RunId(new_ulid())
    saved = report(run_id)
    store.save_report(saved)
    assert store.load_report(run_id) == saved


def test_load_missing_returns_none(store: RunStorePort) -> None:
    assert store.load_report(RunId(new_ulid())) is None


def test_saving_again_overwrites(store: RunStorePort) -> None:
    run_id = RunId(new_ulid())
    store.save_report(report(run_id))
    updated = report(run_id, speculative=True)
    store.save_report(updated)
    assert store.load_report(run_id) == updated


def test_all_fields_survive_a_roundtrip(store: RunStorePort) -> None:
    run_id = RunId(new_ulid())
    store.save_report(report(run_id, speculative=True))
    loaded = store.load_report(run_id)
    assert loaded is not None
    (finding,) = loaded.findings
    assert finding.speculative is True
    assert finding.confidence == pytest.approx(0.7)
    assert finding.citations == ("src/refunds/webhook.py:84-121 @ ffffffffffff",)
    assert loaded.missing_information == ("no logs were available",)


def test_list_recent_is_newest_first(store: RunStorePort) -> None:
    older, newer = RunId(new_ulid()), RunId(new_ulid())
    store.save_report(report(older))
    store.save_report(report(newer))
    listed = [r.run_id for r in store.list_recent()]
    assert listed == sorted((older, newer), reverse=True)


def test_list_recent_respects_the_limit(store: RunStorePort) -> None:
    for _ in range(4):
        store.save_report(report(RunId(new_ulid())))
    assert len(list(store.list_recent(limit=2))) == 2


def test_list_recent_is_empty_for_a_fresh_store(store: RunStorePort) -> None:
    assert list(store.list_recent()) == []
