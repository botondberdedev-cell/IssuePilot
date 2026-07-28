"""The suite runner: scoring every case, gating, and surviving failures."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from issuepilot.evaluation.application.use_cases.run_suite import RunSuite
from issuepilot.evaluation.domain.events import EvaluationCompleted, QualityGateFailed
from issuepilot.evaluation.domain.gate import DEFAULT_GATE, QualityGate, Threshold
from issuepilot.shared_kernel.cancellation import CancellationToken
from issuepilot.shared_kernel.clock import FixedClock
from issuepilot.shared_kernel.errors import OperationInterruptedError
from issuepilot.shared_kernel.ids import UlidGenerator
from tests.support.fakes.evaluation import (
    FakeExperimentTracker,
    InMemoryDatasetRepository,
    ScriptedCaseRunner,
    bad_report,
    good_report,
    sample_case,
)
from tests.support.fakes.eventbus import RecordingEventBus


def build(
    *,
    cases: list[str] | None = None,
    reports: dict[str, object] | None = None,
    failing: set[str] | None = None,
    gate: QualityGate | None = None,
) -> tuple[RunSuite, ScriptedCaseRunner, FakeExperimentTracker, RecordingEventBus]:
    names = cases or ["case-1", "case-2"]
    datasets = InMemoryDatasetRepository([sample_case(n) for n in names])
    runner = ScriptedCaseRunner(reports or {}, failing)  # type: ignore[arg-type]
    tracker = FakeExperimentTracker()
    bus = RecordingEventBus()
    suite = RunSuite(
        datasets=datasets,
        runner=runner,
        gate=gate or DEFAULT_GATE,
        tracker=tracker,
        ids=UlidGenerator(),
        clock=FixedClock(datetime(2026, 7, 28, tzinfo=UTC)),
        bus=bus,
    )
    return suite, runner, tracker, bus


class TestRunning:
    def test_every_case_is_run_and_scored(self) -> None:
        suite, runner, _, _ = build()
        result = suite.execute("fake")
        assert runner.ran == ["case-1", "case-2"]
        assert len(result.scores) == 2

    def test_a_clean_suite_passes_the_gate(self) -> None:
        suite, _, _, _ = build()
        assert suite.execute("fake").passed

    def test_a_bad_citation_fails_the_gate(self) -> None:
        suite, _, _, _ = build(reports={"case-2": bad_report()})
        result = suite.execute("fake")
        assert not result.passed
        assert any(f.metric == "citation-validity" for f in result.verdict.failures)

    def test_progress_is_reported_per_case(self) -> None:
        seen: list[str] = []
        suite, _, _, _ = build()
        suite.execute("fake", on_case=lambda score: seen.append(score.case_id))
        assert seen == ["case-1", "case-2"]


class TestResilience:
    def test_a_crashing_case_scores_zero_without_aborting_the_suite(self) -> None:
        """One broken case must not hide the other forty-nine."""
        suite, runner, _, _ = build(cases=["case-1", "case-2", "case-3"], failing={"case-2"})
        result = suite.execute("fake")
        assert runner.ran == ["case-1", "case-2", "case-3"]
        assert len(result.scores) == 3
        assert not result.passed

    def test_the_crash_is_reported_not_swallowed(self) -> None:
        suite, _, _, _ = build(failing={"case-2"})
        result = suite.execute("fake")
        assert any("case-2" in error and "RuntimeError" in error for error in result.errors)

    def test_cancellation_stops_the_suite(self) -> None:
        suite, runner, _, _ = build()
        token = CancellationToken()
        token.cancel()
        with pytest.raises(OperationInterruptedError):
            suite.execute("fake", cancellation=token)
        assert runner.ran == []


class TestLineage:
    def test_the_run_is_tracked_with_dataset_parameters(self) -> None:
        suite, _, tracker, _ = build()
        suite.execute("fake")
        (run,) = tracker.runs
        assert run.params["dataset"] == "fake"
        assert run.params["case_count"] == "2"
        assert "citation-validity" in run.metrics

    def test_the_dataset_hash_is_stable_for_the_same_cases(self) -> None:
        first = build()[0].execute("fake")
        second = build()[0].execute("fake")
        assert first.dataset_hash == second.dataset_hash

    def test_the_dataset_hash_changes_when_cases_change(self) -> None:
        first = build(cases=["case-1"])[0].execute("fake")
        second = build(cases=["case-1", "case-2"])[0].execute("fake")
        assert first.dataset_hash != second.dataset_hash


class TestEvents:
    def test_completion_is_always_published(self) -> None:
        suite, _, _, bus = build()
        suite.execute("fake")
        assert any(isinstance(e, EvaluationCompleted) for e in bus.published)

    def test_a_gate_failure_publishes_the_failing_metric(self) -> None:
        suite, _, _, bus = build(reports={"case-2": bad_report()})
        suite.execute("fake")
        failures = [e for e in bus.published if isinstance(e, QualityGateFailed)]
        assert any(e.gate_name == "citation-validity" for e in failures)

    def test_a_passing_run_publishes_no_failure(self) -> None:
        suite, _, _, bus = build()
        suite.execute("fake")
        assert not any(isinstance(e, QualityGateFailed) for e in bus.published)


class TestGateIntegration:
    def test_an_advisory_threshold_does_not_block(self) -> None:
        lenient = QualityGate(
            name="lenient",
            thresholds=(Threshold(metric="pass-rate", minimum=0.99, mandatory=False),),
        )
        suite, _, _, _ = build(reports={"case-2": bad_report()}, gate=lenient)
        assert suite.execute("fake").passed

    def test_reports_used_for_scoring_come_from_the_runner(self) -> None:
        suite, _, _, _ = build(reports={"case-1": good_report(), "case-2": good_report()})
        assert suite.execute("fake").metrics["citation-validity"] == 1.0
