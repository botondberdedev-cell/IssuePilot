"""SQLite-backed report storage.

Findings are stored as JSON in one column rather than a normalized table:
a report is always read whole, never queried by finding, and keeping it as
one document avoids a join that would buy nothing.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence

from issuepilot.investigation.application.dto import FindingDTO, ReportDTO
from issuepilot.shared_kernel.ids import RunId


class SqliteRunStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def save_report(self, report: ReportDTO) -> None:
        self._connection.execute(
            "INSERT OR REPLACE INTO inv_reports"
            " (run_id, report_id, commit_sha, issue_summary, completeness,"
            "  findings, missing_information)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                report.run_id,
                report.report_id,
                report.commit_sha,
                report.issue_summary,
                report.completeness,
                json.dumps([_finding_to_json(f) for f in report.findings]),
                json.dumps(list(report.missing_information)),
            ),
        )

    def load_report(self, run_id: RunId) -> ReportDTO | None:
        row = self._connection.execute(
            "SELECT * FROM inv_reports WHERE run_id = ?", (run_id,)
        ).fetchone()
        return _to_report(row) if row is not None else None

    def list_recent(self, limit: int = 20) -> Sequence[ReportDTO]:
        # Run ids are ULIDs, so descending id order is newest first.
        rows = self._connection.execute(
            "SELECT * FROM inv_reports ORDER BY run_id DESC LIMIT ?", (limit,)
        ).fetchall()
        return tuple(_to_report(row) for row in rows)


def _finding_to_json(finding: FindingDTO) -> dict[str, object]:
    return {
        "claim": finding.claim,
        "confidence": finding.confidence,
        "citations": list(finding.citations),
        "speculative": finding.speculative,
    }


def _to_report(row: sqlite3.Row) -> ReportDTO:
    findings = tuple(
        FindingDTO(
            claim=str(entry["claim"]),
            confidence=float(entry["confidence"]),
            citations=tuple(str(c) for c in entry["citations"]),
            speculative=bool(entry["speculative"]),
        )
        for entry in json.loads(row["findings"])
    )
    return ReportDTO(
        report_id=row["report_id"],
        run_id=row["run_id"],
        commit_sha=row["commit_sha"],
        issue_summary=row["issue_summary"],
        completeness=row["completeness"],
        findings=findings,
        missing_information=tuple(json.loads(row["missing_information"])),
    )
