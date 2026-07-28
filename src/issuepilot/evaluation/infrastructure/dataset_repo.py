"""Evaluation datasets loaded from JSONL files.

JSONL rather than one large document: a case is one line, so a diff shows
exactly which cases changed, and adding a case never reformats the rest.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from issuepilot.evaluation.domain.case import (
    CaseCategory,
    Difficulty,
    EvaluationCase,
    EvaluationDataset,
)
from issuepilot.shared_kernel.errors import UsageError
from issuepilot.shared_kernel.ids import EvalCaseId

DATASET_VERSION = "1.0.0"


class JsonlDatasetRepository:
    def __init__(self, root: Path) -> None:
        self._root = root

    def available(self) -> Sequence[str]:
        if not self._root.is_dir():
            return ()
        return tuple(sorted(p.stem for p in self._root.glob("*.jsonl")))

    def load(self, name: str) -> EvaluationDataset:
        path = self._root / f"{name}.jsonl"
        if not path.is_file():
            available = ", ".join(self.available()) or "none"
            raise UsageError(
                f"no evaluation dataset named {name!r}",
                remediation=f"available datasets: {available}",
            )
        cases = [
            _to_case(line_number, json.loads(line))
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            )
            if line.strip()
        ]
        return EvaluationDataset(version=DATASET_VERSION, cases=tuple(cases))


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value)


def _to_case(line_number: int, payload: dict[str, object]) -> EvaluationCase:
    try:
        return EvaluationCase(
            case_id=EvalCaseId(str(payload["case_id"])),
            issue=str(payload["issue"]),
            category=CaseCategory(str(payload["category"])),
            fixture=str(payload["fixture"]),
            expected_paths=_strings(payload.get("expected_paths")),
            forbidden_claims=_strings(payload.get("forbidden_claims")),
            expect_incomplete=bool(payload.get("expect_incomplete", False)),
            difficulty=Difficulty(str(payload.get("difficulty", "medium"))),
            tags=_strings(payload.get("tags")),
        )
    except (KeyError, ValueError) as exc:
        raise UsageError(f"malformed evaluation case on line {line_number}: {exc}") from exc
