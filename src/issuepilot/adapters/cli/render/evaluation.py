"""Renderers for evaluation results."""

from __future__ import annotations

from typing import Any

from issuepilot.adapters.cli.console import Console
from issuepilot.evaluation.application.dto import SuiteResultDTO

FORMAT_VERSION = 1


def suite_json(result: SuiteResultDTO) -> dict[str, Any]:
    return {
        "format_version": FORMAT_VERSION,
        "evaluation_run_id": result.evaluation_run_id,
        "dataset": result.dataset,
        "dataset_hash": result.dataset_hash,
        "passed": result.passed,
        "metrics": {k: round(v, 6) for k, v in result.metrics.items()},
        "thresholds": [
            {
                "metric": t.metric,
                "required": t.required,
                "actual": t.actual,
                "met": t.met,
                "mandatory": t.mandatory,
            }
            for t in result.thresholds
        ],
        "cases": [
            {
                "case_id": c.case_id,
                "category": c.category,
                "passed": c.passed,
                **dict(c.metrics),
            }
            for c in result.cases
        ],
        "errors": list(result.errors),
    }


def suite_terminal(result: SuiteResultDTO, console: Console) -> str:
    headline = "PASSED" if result.passed else "FAILED"
    lines = [
        f"{console.style(headline, 'green' if result.passed else 'red')}  {result.dataset} "
        f"({len(result.cases)} cases, dataset {result.dataset_hash[:12]})",
        "",
    ]

    if result.failing_cases:
        lines.append(console.style("failing cases", "bold"))
        lines.extend(
            f"  {case.case_id:<26} {case.category:<22} {', '.join(case.weak_metrics())}"
            for case in result.failing_cases
        )
        lines.append("")

    lines.append(console.style("gate", "bold"))
    lines.extend(f"  {t.describe()}" for t in result.thresholds)

    if result.errors:
        lines.extend(["", console.style("errors", "bold")])
        lines.extend(f"  {error}" for error in result.errors)
    return "\n".join(lines)
