"""Contract suite for RunStorePort (SQLite adapter joins in v0.1)."""

from __future__ import annotations

import pytest

from issuepilot.investigation.application.dto import FindingDTO, ReportDTO
from issuepilot.investigation.application.ports import RunStorePort
from issuepilot.shared_kernel.ids import RunId, new_ulid
from tests.support.fakes.run_store import InMemoryRunStore


@pytest.fixture(params=["fake"])
def store(request: pytest.FixtureRequest) -> RunStorePort:
    return InMemoryRunStore()


def _report(run_id: str) -> ReportDTO:
    return ReportDTO(
        report_id=new_ulid(),
        run_id=run_id,
        commit_sha="f" * 40,
        issue_summary="refunds stuck",
        completeness="complete",
        findings=(
            FindingDTO(
                claim="the retry path drops the state transition",
                confidence=0.7,
                citations=("src/refunds/webhook.py:84-121 @ ffffffffffff",),
                speculative=False,
            ),
        ),
        missing_information=(),
    )


def test_save_load_roundtrip(store: RunStorePort) -> None:
    run_id = RunId(new_ulid())
    report = _report(run_id)
    store.save_report(report)
    assert store.load_report(run_id) == report


def test_load_missing_returns_none(store: RunStorePort) -> None:
    assert store.load_report(RunId(new_ulid())) is None


def test_saving_again_overwrites(store: RunStorePort) -> None:
    run_id = RunId(new_ulid())
    store.save_report(_report(run_id))
    updated = _report(run_id)
    store.save_report(updated)
    assert store.load_report(run_id) == updated
