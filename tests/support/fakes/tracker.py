from __future__ import annotations

from issuepilot.evaluation.application.ports import TrackedRun


class FakeExperimentTracker:
    def __init__(self) -> None:
        self.runs: list[TrackedRun] = []

    def log_run(self, run: TrackedRun) -> None:
        self.runs.append(run)
