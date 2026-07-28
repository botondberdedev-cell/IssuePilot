"""Experiment tracking.

Two implementations, both satisfying ExperimentTrackerPort. The JSONL tracker
is the default so lineage is recorded with no extra dependency; MLflow is an
optional extra, imported lazily so its large dependency tree never loads for
a user who does not want it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from issuepilot.evaluation.application.ports import TrackedRun


class JsonlExperimentTracker:
    """Appends one line per run. Enough for lineage and diffing over time."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def log_run(self, run: TrackedRun) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "name": run.name,
            "params": dict(run.params),
            "metrics": {k: round(v, 6) for k, v in run.metrics.items()},
        }
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


class MlflowExperimentTracker:
    """Optional. Import is deferred to the first call so `import issuepilot`
    never pays for MLflow."""

    def __init__(self, tracking_uri: str, experiment: str = "issuepilot") -> None:
        self._tracking_uri = tracking_uri
        self._experiment = experiment

    def log_run(self, run: TrackedRun) -> None:
        mlflow = _import_mlflow()
        mlflow.set_tracking_uri(self._tracking_uri)
        mlflow.set_experiment(self._experiment)
        with mlflow.start_run(run_name=run.name):
            mlflow.log_params(dict(run.params))
            mlflow.log_metrics(dict(run.metrics))


def _import_mlflow() -> Any:
    try:
        import mlflow
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise RuntimeError(
            "MLflow tracking requested but mlflow is not installed; "
            "install the 'mlflow' extra or use the default JSONL tracker"
        ) from exc
    return mlflow
