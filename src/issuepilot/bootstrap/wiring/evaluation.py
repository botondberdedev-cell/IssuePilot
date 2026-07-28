"""Wires the evaluation context.

The runner translator is what lets evaluation drive real investigations
without importing the investigation context: evaluation declares the narrow
shape it needs (a ScoredReport), and this module produces one by running the
real pipeline and projecting the result.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from issuepilot.evaluation.application.dto import SuiteResultDTO
from issuepilot.evaluation.application.ports import DatasetPort
from issuepilot.evaluation.application.public import EvaluationFacade
from issuepilot.evaluation.application.use_cases.run_suite import RunSuite
from issuepilot.evaluation.domain.case import EvaluationCase
from issuepilot.evaluation.domain.gate import DEFAULT_GATE
from issuepilot.evaluation.domain.scoring import ScoredReport
from issuepilot.evaluation.infrastructure.dataset_repo import JsonlDatasetRepository
from issuepilot.evaluation.infrastructure.mlflow_tracker import JsonlExperimentTracker
from issuepilot.shared_kernel.clock import Clock
from issuepilot.shared_kernel.events import EventBus
from issuepilot.shared_kernel.ids import IdGenerator


class PipelineCaseRunner:
    """Runs one evaluation case through acquisition, indexing, and the agent.

    ``fixture: "self"`` means the repository under test is IssuePilot itself,
    which makes the seed dataset runnable with no external checkout — the
    tool evaluating the tool.
    """

    def __init__(
        self,
        repository: object,
        knowledge: object,
        investigation: object,
        self_path: Path,
        max_steps: int,
    ) -> None:
        self._repository = repository
        self._knowledge = knowledge
        self._investigation = investigation
        self._self_path = self_path
        self._max_steps = max_steps

    def run_case(self, case: EvaluationCase) -> ScoredReport:
        locator = str(self._self_path) if case.fixture == "self" else case.fixture
        snapshot = self._repository.acquire(locator, allow_local_path=True)  # type: ignore[attr-defined]
        self._knowledge.build_index(snapshot.commit_sha, snapshot.root_path)  # type: ignore[attr-defined]
        report = self._investigation.investigate(  # type: ignore[attr-defined]
            case.issue, snapshot.commit_sha, snapshot.root_path, max_steps=self._max_steps
        )
        return _project(report)


def _project(report: object) -> ScoredReport:
    """Project a report DTO onto the narrow shape scoring needs."""
    findings = report.findings  # type: ignore[attr-defined]
    return ScoredReport(
        commit_sha=report.commit_sha,  # type: ignore[attr-defined]
        completeness=report.completeness,  # type: ignore[attr-defined]
        claims=tuple(f.claim for f in findings),
        citations=tuple(c for f in findings for c in f.citations),
        speculative_claims=tuple(f.claim for f in findings if f.speculative),
        missing_information=tuple(report.missing_information),  # type: ignore[attr-defined]
    )


def build_evaluation_facade(
    *,
    connection: sqlite3.Connection,
    dataset_root: Path,
    tracker_path: Path,
    runner: PipelineCaseRunner,
    ids: IdGenerator,
    clock: Clock,
    bus: EventBus,
) -> EvaluationFacade:
    datasets: DatasetPort = JsonlDatasetRepository(dataset_root)
    run_suite = RunSuite(
        datasets=datasets,
        runner=runner,
        gate=DEFAULT_GATE,
        tracker=JsonlExperimentTracker(tracker_path),
        ids=ids,
        clock=clock,
        bus=bus,
    )
    return EvaluationFacade(run_suite, datasets)


class EvaluationServiceAdapter:
    """Presents the evaluation facade in the primitives the CLI speaks."""

    def __init__(self, facade: EvaluationFacade) -> None:
        self._facade = facade

    def run(self, dataset: str, *, on_case: object = None) -> SuiteResultDTO:
        return self._facade.run(dataset, on_case=on_case)

    def available_datasets(self) -> tuple[str, ...]:
        return tuple(self._facade.available_datasets())
