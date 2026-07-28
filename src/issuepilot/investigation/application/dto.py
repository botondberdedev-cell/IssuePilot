"""Immutable DTOs crossing the investigation context's boundary."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EvidenceCandidateDTO:
    """A retrieval hit offered to the strategy as potential evidence."""

    path: str
    start_line: int
    end_line: int
    snippet: str
    score: float
    commit_sha: str


@dataclass(frozen=True, slots=True)
class FindingDTO:
    claim: str
    confidence: float
    citations: tuple[str, ...]
    speculative: bool


@dataclass(frozen=True, slots=True)
class ReportDTO:
    report_id: str
    run_id: str
    commit_sha: str
    issue_summary: str
    completeness: str
    findings: tuple[FindingDTO, ...]
    missing_information: tuple[str, ...]
