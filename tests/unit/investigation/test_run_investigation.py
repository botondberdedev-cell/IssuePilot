from __future__ import annotations

from datetime import UTC, datetime

import pytest

from issuepilot.investigation.application.dto import EvidenceCandidateDTO
from issuepilot.investigation.application.use_cases.run_investigation import RunInvestigation
from issuepilot.investigation.domain.events import InvestigationCompleted, InvestigationStarted
from issuepilot.investigation.domain.values import IssueStatement
from issuepilot.shared_kernel.cancellation import CancellationToken
from issuepilot.shared_kernel.clock import FixedClock
from issuepilot.shared_kernel.errors import EvidenceRequirementError, OperationInterruptedError
from issuepilot.shared_kernel.ids import UlidGenerator
from tests.support.fakes.citations import FakeCitationVerifier
from tests.support.fakes.eventbus import RecordingEventBus
from tests.support.fakes.reasoning import FakeReasoningModel
from tests.support.fakes.run_store import InMemoryRunStore
from tests.support.fakes.search import FakeSearch

SHA = "a" * 40


def candidate(path: str, score: float = 0.9) -> EvidenceCandidateDTO:
    return EvidenceCandidateDTO(
        path=path, start_line=10, end_line=20, snippet="...", score=score, commit_sha=SHA
    )


def build_use_case(
    *,
    candidates: list[EvidenceCandidateDTO],
    verified: list[EvidenceCandidateDTO] | None = None,
) -> tuple[RunInvestigation, InMemoryRunStore, RecordingEventBus]:
    verifier = FakeCitationVerifier()
    for c in verified if verified is not None else candidates:
        verifier.allow(c.path, c.start_line, c.end_line, c.commit_sha)
    store = InMemoryRunStore()
    bus = RecordingEventBus()
    use_case = RunInvestigation(
        model=FakeReasoningModel(["The retry path drops the state transition."]),
        search=FakeSearch(candidates),
        verifier=verifier,
        store=store,
        ids=UlidGenerator(),
        clock=FixedClock(datetime(2026, 7, 28, tzinfo=UTC)),
        bus=bus,
    )
    return use_case, store, bus


def test_happy_path_produces_persisted_cited_report() -> None:
    use_case, store, bus = build_use_case(candidates=[candidate("src/webhook.py")])
    report = use_case.execute(IssueStatement("Refunds remain pending after retry"), SHA)

    assert report.commit_sha == SHA
    assert report.completeness == "complete"
    (finding,) = report.findings
    assert finding.citations == (f"src/webhook.py:10-20 @ {'a' * 12}",)
    assert not finding.speculative
    assert store.load_report(report.run_id) == report  # type: ignore[arg-type]
    assert [type(e) for e in bus.published] == [InvestigationStarted, InvestigationCompleted]


def test_unverifiable_evidence_fails_the_evidence_requirement() -> None:
    use_case, _, _ = build_use_case(candidates=[candidate("src/webhook.py")], verified=[])
    with pytest.raises(EvidenceRequirementError):
        use_case.execute(IssueStatement("Anything"), SHA)


def test_candidates_from_other_snapshots_never_become_evidence() -> None:
    foreign = EvidenceCandidateDTO(
        path="src/webhook.py",
        start_line=10,
        end_line=20,
        snippet="...",
        score=0.9,
        commit_sha="b" * 40,
    )
    use_case, _, _ = build_use_case(candidates=[foreign])
    with pytest.raises(EvidenceRequirementError):
        use_case.execute(IssueStatement("Anything"), SHA)


def test_cancellation_interrupts_before_model_call() -> None:
    use_case, _, _ = build_use_case(candidates=[candidate("src/webhook.py")])
    token = CancellationToken()
    token.cancel()
    with pytest.raises(OperationInterruptedError):
        use_case.execute(IssueStatement("Anything"), SHA, cancellation=token)
