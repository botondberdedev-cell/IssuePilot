"""The evaluation context's public facade."""

from __future__ import annotations

from collections.abc import Sequence

from issuepilot.evaluation.application.dto import (
    CaseScoreDTO,
    SuiteResultDTO,
    ThresholdResultDTO,
)
from issuepilot.evaluation.application.ports import DatasetPort
from issuepilot.evaluation.application.use_cases.run_suite import RunSuite, SuiteResult
from issuepilot.shared_kernel.cancellation import NEVER_CANCELLED, CancellationToken


class EvaluationFacade:
    def __init__(self, run_suite: RunSuite, datasets: DatasetPort) -> None:
        self._run_suite = run_suite
        self._datasets = datasets

    def run(
        self,
        dataset: str,
        *,
        cancellation: CancellationToken = NEVER_CANCELLED,
        on_case: object = None,
    ) -> SuiteResultDTO:
        result = self._run_suite.execute(dataset, cancellation=cancellation, on_case=on_case)
        return to_dto(result)

    def available_datasets(self) -> Sequence[str]:
        return self._datasets.available()

    def describe(self, dataset: str) -> dict[str, int]:
        return self._datasets.load(dataset).category_counts()


def to_dto(result: SuiteResult) -> SuiteResultDTO:
    return SuiteResultDTO(
        evaluation_run_id=result.evaluation_run_id,
        dataset=result.dataset,
        dataset_hash=result.dataset_hash,
        passed=result.passed,
        metrics=dict(result.metrics),
        thresholds=tuple(
            ThresholdResultDTO(
                metric=r.metric,
                required=r.required,
                actual=r.actual,
                met=r.met,
                mandatory=r.mandatory,
            )
            for r in result.verdict.results
        ),
        cases=tuple(
            CaseScoreDTO(
                case_id=score.case_id,
                category=score.category,
                passed=score.passed,
                metrics=score.as_dict(),
            )
            for score in result.scores
        ),
        errors=result.errors,
    )
