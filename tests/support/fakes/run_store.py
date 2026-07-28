from __future__ import annotations

from issuepilot.investigation.application.dto import ReportDTO
from issuepilot.shared_kernel.ids import RunId


class InMemoryRunStore:
    def __init__(self) -> None:
        self._reports: dict[str, ReportDTO] = {}

    def save_report(self, report: ReportDTO) -> None:
        self._reports[report.run_id] = report

    def load_report(self, run_id: RunId) -> ReportDTO | None:
        return self._reports.get(run_id)
