"""Ports required by investigation use cases.

Every Protocol here must have a fake in ``tests/support/fakes`` and a
contract suite in ``tests/contract`` (enforced by the arch conventions test).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from issuepilot.investigation.application.dto import EvidenceCandidateDTO, ReportDTO
from issuepilot.shared_kernel.ids import RunId


@dataclass(frozen=True, slots=True)
class ModelRequest:
    """A single completion request. v0.1 refines this to named prompt +
    schema pairs once the prompt registry lands."""

    prompt: str


class ReasoningModelPort(Protocol):
    def complete(self, request: ModelRequest) -> str: ...


class SearchPort(Protocol):
    """Evidence retrieval, served by the knowledge context via a translator."""

    def search(self, query: str, *, limit: int) -> Sequence[EvidenceCandidateDTO]: ...


class CitationVerifierPort(Protocol):
    """Citation validity, served by the repository context via a translator."""

    def verify(self, path: str, start_line: int, end_line: int, commit_sha: str) -> bool: ...


class RunStorePort(Protocol):
    def save_report(self, report: ReportDTO) -> None: ...

    def load_report(self, run_id: RunId) -> ReportDTO | None: ...
