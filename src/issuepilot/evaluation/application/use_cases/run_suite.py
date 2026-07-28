"""Run an evaluation suite and apply the gate.

A case that raises is scored as a failure rather than aborting the suite: one
broken case should not hide the result of the other forty-nine, and "it
crashed" is itself a quality signal worth recording.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from issuepilot.evaluation.application.ports import (
    DatasetPort,
    ExperimentTrackerPort,
    InvestigationRunnerPort,
    TrackedRun,
)
from issuepilot.evaluation.domain.case import EvaluationCase
from issuepilot.evaluation.domain.events import EvaluationCompleted, QualityGateFailed
from issuepilot.evaluation.domain.gate import GateVerdict, QualityGate
from issuepilot.evaluation.domain.scoring import CaseScore, ScoredReport, aggregate, score_case
from issuepilot.shared_kernel.cancellation import NEVER_CANCELLED, CancellationToken
from issuepilot.shared_kernel.clock import Clock
from issuepilot.shared_kernel.events import EventBus
from issuepilot.shared_kernel.hashing import canonical_json_hash
from issuepilot.shared_kernel.ids import EvalRunId, EventId, IdGenerator


@dataclass(frozen=True, slots=True)
class SuiteResult:
    evaluation_run_id: str
    dataset: str
    dataset_hash: str
    scores: tuple[CaseScore, ...]
    metrics: dict[str, float]
    verdict: GateVerdict
    errors: tuple[str, ...] = field(default=())

    @property
    def passed(self) -> bool:
        return self.verdict.passed


class RunSuite:
    def __init__(
        self,
        *,
        datasets: DatasetPort,
        runner: InvestigationRunnerPort,
        gate: QualityGate,
        tracker: ExperimentTrackerPort,
        ids: IdGenerator,
        clock: Clock,
        bus: EventBus,
    ) -> None:
        self._datasets = datasets
        self._runner = runner
        self._gate = gate
        self._tracker = tracker
        self._ids = ids
        self._clock = clock
        self._bus = bus

    def execute(
        self,
        dataset_name: str,
        *,
        cancellation: CancellationToken = NEVER_CANCELLED,
        on_case: object = None,
    ) -> SuiteResult:
        dataset = self._datasets.load(dataset_name)
        run_id = EvalRunId(self._ids.new_id())

        scores: list[CaseScore] = []
        errors: list[str] = []
        for case in dataset.cases:
            cancellation.raise_if_cancelled()
            score, error = self._score_one(case)
            scores.append(score)
            if error is not None:
                errors.append(error)
            if callable(on_case):
                on_case(score)

        metrics = aggregate(scores)
        verdict = self._gate.evaluate(metrics)

        self._tracker.log_run(
            TrackedRun(
                name=f"{dataset.version}:{dataset_name}",
                params={
                    "dataset": dataset_name,
                    "dataset_version": dataset.version,
                    "case_count": str(len(dataset)),
                    "gate": self._gate.name,
                },
                metrics=metrics,
            )
        )
        self._publish(run_id, dataset_name, len(dataset), verdict)

        return SuiteResult(
            evaluation_run_id=run_id,
            dataset=dataset_name,
            dataset_hash=_dataset_hash(dataset.version, dataset.cases),
            scores=tuple(scores),
            metrics=metrics,
            verdict=verdict,
            errors=tuple(errors),
        )

    def _score_one(self, case: EvaluationCase) -> tuple[CaseScore, str | None]:
        try:
            report = self._runner.run_case(case)
        except Exception as exc:  # a crashed case is a failed case, not a lost suite
            return _zero_score(case), f"{case.case_id}: {type(exc).__name__}: {exc}"
        return score_case(case, report), None

    def _publish(
        self, run_id: EvalRunId, dataset: str, case_count: int, verdict: GateVerdict
    ) -> None:
        self._bus.publish(
            EvaluationCompleted(
                event_id=EventId(self._ids.new_id()),
                occurred_at=self._clock.now(),
                aggregate_id=run_id,
                evaluation_run_id=run_id,
                case_count=case_count,
            )
        )
        if not verdict.passed:
            for failure in verdict.failures:
                if not failure.mandatory:
                    continue
                self._bus.publish(
                    QualityGateFailed(
                        event_id=EventId(self._ids.new_id()),
                        occurred_at=self._clock.now(),
                        aggregate_id=run_id,
                        evaluation_run_id=run_id,
                        gate_name=failure.metric,
                    )
                )


def _zero_score(case: EvaluationCase) -> CaseScore:
    return CaseScore(
        case_id=case.case_id,
        category=case.category.value,
        citation_validity=0.0,
        required_path_recall=0.0,
        claim_grounding=0.0,
        forbidden_claim_absence=0.0,
        honesty=0.0,
    )


def _dataset_hash(version: str, cases: tuple[EvaluationCase, ...]) -> str:
    """Lineage: a result is only comparable to another from the same cases."""
    return canonical_json_hash(
        {
            "version": version,
            "cases": [
                {
                    "id": c.case_id,
                    "issue": c.issue,
                    "category": c.category.value,
                    "expected_paths": list(c.expected_paths),
                    "forbidden_claims": list(c.forbidden_claims),
                    "expect_incomplete": c.expect_incomplete,
                }
                for c in cases
            ],
        }
    )


__all__ = ["RunSuite", "ScoredReport", "SuiteResult"]
