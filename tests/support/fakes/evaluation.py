"""Fakes for the evaluation context's ports."""

from __future__ import annotations

from collections.abc import Sequence

from issuepilot.evaluation.application.ports import TrackedRun
from issuepilot.evaluation.domain.case import (
    CaseCategory,
    EvaluationCase,
    EvaluationDataset,
)
from issuepilot.evaluation.domain.scoring import ScoredReport
from issuepilot.shared_kernel.ids import EvalCaseId

SHA = "4f2a7c1b9e83" + "0" * 28


def sample_case(case_id: str = "case-1", **overrides: object) -> EvaluationCase:
    defaults: dict[str, object] = {
        "case_id": EvalCaseId(case_id),
        "issue": "Where is the retry handled?",
        "category": CaseCategory.BUG_LOCATION,
        "fixture": "self",
        "expected_paths": ("webhook.py",),
    }
    return EvaluationCase(**(defaults | overrides))  # type: ignore[arg-type]


def good_report() -> ScoredReport:
    return ScoredReport(
        commit_sha=SHA,
        completeness="complete",
        claims=("The retry path drops the transition.",),
        citations=(f"src/webhook.py:84-121 @ {SHA[:12]}",),
        speculative_claims=(),
        missing_information=(),
    )


def bad_report() -> ScoredReport:
    return ScoredReport(
        commit_sha=SHA,
        completeness="complete",
        claims=("Something unfounded.",),
        citations=("not a real citation",),
        speculative_claims=(),
        missing_information=(),
    )


class InMemoryDatasetRepository:
    def __init__(self, cases: Sequence[EvaluationCase] = (), version: str = "1.0.0") -> None:
        self._dataset = EvaluationDataset(version=version, cases=tuple(cases))

    def load(self, name: str) -> EvaluationDataset:
        return self._dataset

    def available(self) -> Sequence[str]:
        return ("fake",)


class ScriptedCaseRunner:
    """Returns a scripted report per case id, or raises for ids in ``failing``."""

    def __init__(
        self,
        reports: dict[str, ScoredReport] | None = None,
        failing: set[str] | None = None,
    ) -> None:
        self._reports = reports or {}
        self._failing = failing or set()
        self.ran: list[str] = []

    def run_case(self, case: EvaluationCase) -> ScoredReport:
        self.ran.append(case.case_id)
        if case.case_id in self._failing:
            raise RuntimeError(f"case {case.case_id} blew up")
        return self._reports.get(case.case_id, good_report())


class FakeExperimentTracker:
    def __init__(self) -> None:
        self.runs: list[TrackedRun] = []

    def log_run(self, run: TrackedRun) -> None:
        self.runs.append(run)
