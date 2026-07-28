"""Milestone-0 exit criterion: a fake end-to-end investigation completes
through the public facade — no Git process, no Ollama, no network."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from issuepilot.investigation.application.dto import EvidenceCandidateDTO
from issuepilot.investigation.application.public import InvestigationFacade
from issuepilot.investigation.application.use_cases.run_investigation import RunInvestigation
from issuepilot.shared_kernel.clock import FixedClock
from issuepilot.shared_kernel.ids import UlidGenerator
from tests.support.fakes.citations import FakeCitationVerifier
from tests.support.fakes.eventbus import RecordingEventBus
from tests.support.fakes.reasoning import FakeReasoningModel
from tests.support.fakes.run_store import InMemoryRunStore
from tests.support.fakes.search import FakeSearch

pytestmark = pytest.mark.e2e

SHA = "4f2a7c" + "0" * 34


def test_fake_investigation_end_to_end() -> None:
    candidates = [
        EvidenceCandidateDTO(
            path="src/refunds/webhook.py",
            start_line=84,
            end_line=121,
            snippet="def handle_retry(...)",
            score=0.92,
            commit_sha=SHA,
        ),
        EvidenceCandidateDTO(
            path="src/refunds/state.py",
            start_line=33,
            end_line=59,
            snippet="class RefundState(...)",
            score=0.81,
            commit_sha=SHA,
        ),
    ]
    verifier = FakeCitationVerifier()
    for c in candidates:
        verifier.allow(c.path, c.start_line, c.end_line, c.commit_sha)

    store = InMemoryRunStore()
    facade = InvestigationFacade(
        RunInvestigation(
            model=FakeReasoningModel(
                ["The retry path deduplicates the event before the state transition commits."]
            ),
            search=FakeSearch(candidates),
            verifier=verifier,
            store=store,
            ids=UlidGenerator(),
            clock=FixedClock(datetime(2026, 7, 28, tzinfo=UTC)),
            bus=RecordingEventBus(),
        )
    )

    report = facade.investigate(
        "Refunds remain pending after a webhook retry.\n\nSeen since v2.4.",
        SHA,
    )

    assert report.commit_sha == SHA
    assert report.issue_summary == "Refunds remain pending after a webhook retry."
    assert report.completeness == "complete"
    (finding,) = report.findings
    assert "state transition" in finding.claim
    assert finding.citations == (
        "src/refunds/webhook.py:84-121 @ 4f2a7c000000",
        "src/refunds/state.py:33-59 @ 4f2a7c000000",
    )
