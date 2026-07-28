"""The synthesis boundary: verified evidence in, invariant-checked report out.

These tests script the model saying things that must NOT reach a report
unchallenged — citing evidence that does not exist, claiming without citing,
producing nothing at all — and assert the use case constrains each.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from issuepilot.investigation.application.dto import EvidenceCandidateDTO
from issuepilot.investigation.application.strategies.react import ReActStrategy
from issuepilot.investigation.application.use_cases.run_investigation import (
    InvestigateCommand,
    RunInvestigation,
)
from issuepilot.investigation.domain.events import (
    InvestigationCompleted,
    InvestigationStarted,
)
from issuepilot.investigation.domain.values import IssueStatement
from issuepilot.shared_kernel.clock import FixedClock
from issuepilot.shared_kernel.errors import EvidenceRequirementError
from issuepilot.shared_kernel.ids import UlidGenerator
from tests.support.fakes.eventbus import RecordingEventBus
from tests.support.fakes.investigation import (
    FakeCitationVerifier,
    FakeFileReader,
    FakePrompts,
    FakeSearch,
    InMemoryRunStore,
    ScriptedReasoningModel,
)

SHA = "a" * 40
ISSUE = IssueStatement("Refunds remain pending after a webhook retry.")

FIND = {"reason": "look", "tool": "search_text", "query": "handle_retry"}
STOP = {"reason": "done", "tool": "finish"}


def candidate(path: str = "src/webhook.py") -> EvidenceCandidateDTO:
    return EvidenceCandidateDTO(
        path=path,
        start_line=84,
        end_line=121,
        snippet="def handle_retry(event):\n    ...\n",
        score=0.9,
        commit_sha=SHA,
        symbol="handle_retry",
    )


class Harness:
    def __init__(
        self,
        replies: list[dict[str, Any]],
        *,
        candidates: list[EvidenceCandidateDTO] | None = None,
        verify_all: bool = True,
    ) -> None:
        self.model = ScriptedReasoningModel(replies)
        self.prompts = FakePrompts()
        self.search = FakeSearch(candidates if candidates is not None else [candidate()])
        self.verifier = FakeCitationVerifier()
        self.verifier.allow_all = verify_all
        self.store = InMemoryRunStore()
        self.bus = RecordingEventBus()

        def make_strategy(commit_sha: str) -> ReActStrategy:
            return ReActStrategy(
                model=self.model,
                prompts=self.prompts,
                search=self.search,
                reader=FakeFileReader(),
                verifier=self.verifier,
                commit_sha=commit_sha,
            )

        self.use_case = RunInvestigation(
            strategy_factory=make_strategy,
            model=self.model,
            prompts=self.prompts,
            verifier=self.verifier,
            store=self.store,
            ids=UlidGenerator(),
            clock=FixedClock(datetime(2026, 7, 28, tzinfo=UTC)),
            bus=self.bus,
        )

    def run(self, max_steps: int = 5) -> Any:
        return self.use_case.execute(
            InvestigateCommand(issue=ISSUE, commit_sha=SHA, max_steps=max_steps)
        )


def report_reply(findings: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    return {"summary": "Refund retries drop the transition.", "findings": findings, **extra}


class TestHappyPath:
    def _harness(self) -> Harness:
        return Harness(
            [
                FIND,
                STOP,
                report_reply(
                    [
                        {
                            "claim": "The retry path returns before the transition commits.",
                            "confidence": 0.8,
                            "evidence_indices": [0],
                        }
                    ]
                ),
            ]
        )

    def test_produces_a_cited_report(self) -> None:
        report = self._harness().run()
        (finding,) = report.findings
        assert finding.citations == (f"src/webhook.py:84-121 @ {'a' * 12}",)
        assert not finding.speculative

    def test_report_is_pinned_to_the_snapshot(self) -> None:
        assert self._harness().run().commit_sha == SHA

    def test_report_is_persisted(self) -> None:
        harness = self._harness()
        report = harness.run()
        assert harness.store.load_report(report.run_id) == report

    def test_events_bracket_the_run(self) -> None:
        harness = self._harness()
        harness.run()
        assert [type(e) for e in harness.bus.published] == [
            InvestigationStarted,
            InvestigationCompleted,
        ]

    def test_both_prompts_are_used(self) -> None:
        harness = self._harness()
        harness.run()
        assert "react_step@v1" in harness.model.prompts_seen
        assert "report@v1" in harness.model.prompts_seen


class TestEvidenceDiscipline:
    def test_a_claim_citing_nothing_is_marked_speculation(self) -> None:
        harness = Harness(
            [
                FIND,
                STOP,
                report_reply(
                    [
                        {
                            "claim": "I believe it is a race condition.",
                            "confidence": 0.9,
                            "evidence_indices": [],
                        }
                    ]
                ),
            ]
        )
        (finding,) = harness.run().findings
        assert finding.speculative
        assert finding.citations == ()

    def test_an_invented_evidence_index_is_dropped(self) -> None:
        """The model cannot conjure a citation by naming an index we never gave."""
        harness = Harness(
            [
                FIND,
                STOP,
                report_reply(
                    [
                        {
                            "claim": "Something in a file that was never retrieved.",
                            "confidence": 0.9,
                            "evidence_indices": [42],
                        }
                    ]
                ),
            ]
        )
        (finding,) = harness.run().findings
        assert finding.citations == ()
        assert finding.speculative

    def test_unverifiable_evidence_fails_the_run(self) -> None:
        harness = Harness([FIND, STOP], verify_all=False)
        with pytest.raises(EvidenceRequirementError):
            harness.run()

    def test_evidence_from_another_snapshot_fails_the_run(self) -> None:
        foreign = EvidenceCandidateDTO(
            path="other.py",
            start_line=1,
            end_line=2,
            snippet="x",
            score=1.0,
            commit_sha="b" * 40,
        )
        harness = Harness([FIND, STOP], candidates=[foreign])
        with pytest.raises(EvidenceRequirementError):
            harness.run()

    def test_confidence_out_of_range_is_clamped(self) -> None:
        harness = Harness(
            [
                FIND,
                STOP,
                report_reply(
                    [{"claim": "Overconfident.", "confidence": 7.5, "evidence_indices": [0]}]
                ),
            ]
        )
        (finding,) = harness.run().findings
        assert finding.confidence == 1.0

    def test_no_findings_yields_an_admission_not_an_invented_claim(self) -> None:
        """Fabricating a finding here would be the exact failure this product
        exists to prevent."""
        harness = Harness([FIND, STOP, report_reply([])])
        report = harness.run()
        assert report.findings == ()
        assert report.missing_information

    def test_the_models_own_explanation_is_kept_when_it_gives_one(self) -> None:
        harness = Harness(
            [
                FIND,
                STOP,
                report_reply([], missing_information=["The repository has no such module."]),
            ]
        )
        report = harness.run()
        assert report.findings == ()
        assert "no such module" in " ".join(report.missing_information)


class TestCompleteness:
    def test_exhausting_the_budget_marks_the_report_partial(self) -> None:
        harness = Harness(
            [
                FIND,
                FIND,
                report_reply([{"claim": "Partial.", "confidence": 0.5, "evidence_indices": [0]}]),
            ]
        )
        report = harness.run(max_steps=2)
        assert report.completeness == "partial"
        assert any("budget" in item.lower() for item in report.missing_information)

    def test_finishing_early_marks_the_report_complete(self) -> None:
        harness = Harness(
            [
                FIND,
                STOP,
                report_reply([{"claim": "Complete.", "confidence": 0.5, "evidence_indices": [0]}]),
            ]
        )
        assert harness.run().completeness == "complete"
