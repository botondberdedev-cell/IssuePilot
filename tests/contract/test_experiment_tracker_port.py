"""Contract suite for ExperimentTrackerPort (MLflow adapter joins in v0.2)."""

from __future__ import annotations

import pytest

from issuepilot.evaluation.application.ports import ExperimentTrackerPort, TrackedRun
from tests.support.fakes.tracker import FakeExperimentTracker


@pytest.fixture(params=["fake"])
def tracker(request: pytest.FixtureRequest) -> FakeExperimentTracker:
    return FakeExperimentTracker()


def test_logged_runs_are_recorded(tracker: FakeExperimentTracker) -> None:
    port: ExperimentTrackerPort = tracker
    run = TrackedRun(
        name="eval-core",
        params={"strategy": "react", "model": "qwen3"},
        metrics={"required-file-recall": 0.8},
    )
    port.log_run(run)
    assert tracker.runs == [run]


def test_runs_are_recorded_in_order(tracker: FakeExperimentTracker) -> None:
    port: ExperimentTrackerPort = tracker
    first = TrackedRun(name="a", params={}, metrics={})
    second = TrackedRun(name="b", params={}, metrics={})
    port.log_run(first)
    port.log_run(second)
    assert [r.name for r in tracker.runs] == ["a", "b"]
