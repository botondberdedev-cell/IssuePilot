"""Renderers for investigation reports.

All three formats project the same DTO. The commit SHA appears in every one
of them, because a claim without the snapshot it was made against is not
reproducible — and reproducibility is the product's whole promise.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from issuepilot.adapters.cli.console import Console
from issuepilot.investigation.application.dto import ReportDTO

FORMAT_VERSION = 1


def report_json(report: ReportDTO) -> dict[str, Any]:
    return {
        "format_version": FORMAT_VERSION,
        "run_id": report.run_id,
        "report_id": report.report_id,
        "commit_sha": report.commit_sha,
        "completeness": report.completeness,
        "issue_summary": report.issue_summary,
        "findings": [
            {
                "claim": finding.claim,
                "confidence": round(finding.confidence, 3),
                "citations": list(finding.citations),
                "speculative": finding.speculative,
            }
            for finding in report.findings
        ],
        "missing_information": list(report.missing_information),
    }


def report_terminal(report: ReportDTO, console: Console) -> str:
    lines = [
        console.style(report.issue_summary, "bold"),
        console.style(f"commit {report.commit_sha}  ({report.completeness})", "dim"),
        "",
    ]
    for index, finding in enumerate(report.findings, start=1):
        marker = "speculation" if finding.speculative else f"confidence {finding.confidence:.2f}"
        lines.append(f"{index}. {finding.claim}")
        lines.append(console.style(f"   {marker}", "dim"))
        lines.extend(f"   evidence: {citation}" for citation in finding.citations)
        lines.append("")
    if report.missing_information:
        lines.append(console.style("Missing information", "bold"))
        lines.extend(f"  - {item}" for item in report.missing_information)
    return "\n".join(lines).rstrip()


def report_markdown(report: ReportDTO) -> str:
    lines = [
        f"# {report.issue_summary}",
        "",
        f"Investigated at commit `{report.commit_sha}` · report is **{report.completeness}**.",
        "",
        "## Findings",
        "",
    ]
    for finding in report.findings:
        qualifier = " _(speculation — no verified evidence)_" if finding.speculative else ""
        lines.append(f"### {finding.claim}{qualifier}")
        lines.append("")
        lines.append(f"Confidence: {finding.confidence:.2f}")
        lines.append("")
        if finding.citations:
            lines.append("Evidence:")
            lines.append("")
            lines.extend(f"- `{citation}`" for citation in finding.citations)
            lines.append("")
    if report.missing_information:
        lines.extend(["## Missing information", ""])
        lines.extend(f"- {item}" for item in report.missing_information)
        lines.append("")
    return "\n".join(lines)


def report_list_terminal(reports: Sequence[ReportDTO], console: Console) -> str:
    if not reports:
        return "no investigations yet — run 'issuepilot investigate <url> --issue ...'"
    header = console.style(f"{'RUN':<28} {'COMMIT':<14} ISSUE", "bold")
    rows = [f"{r.run_id:<28} {r.commit_sha[:12]:<14} {r.issue_summary[:60]}" for r in reports]
    return "\n".join([header, *rows])
