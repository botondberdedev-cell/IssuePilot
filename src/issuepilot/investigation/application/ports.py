"""Ports required by investigation use cases.

Every Protocol here must have a fake in ``tests/support/fakes`` and a
contract suite in ``tests/contract`` (enforced by the arch conventions test).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from issuepilot.investigation.application.dto import EvidenceCandidateDTO, ReportDTO
from issuepilot.shared_kernel.ids import RunId


@dataclass(frozen=True, slots=True)
class StructuredRequest:
    """A schema-constrained completion, named by prompt rather than carried as
    loose text, so a run's lineage is recorded rather than reconstructed."""

    prompt_name: str
    system: str
    user: str
    schema: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class StructuredReply:
    data: Mapping[str, Any]
    prompt_tokens: int = 0
    completion_tokens: int = 0
    repairs: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class ReasoningModelPort(Protocol):
    """Schema-constrained generation. Implementations return data matching the
    request's schema, or raise — never partial or unvalidated output."""

    def generate(self, request: StructuredRequest) -> StructuredReply: ...


@dataclass(frozen=True, slots=True)
class RenderedPrompt:
    name: str
    version: str
    template_hash: str
    text: str
    schema: Mapping[str, Any] = field(default_factory=dict)


class PromptPort(Protocol):
    def render(self, name: str, **context: Any) -> RenderedPrompt: ...


class SearchPort(Protocol):
    """Evidence retrieval, served by the knowledge context via a translator."""

    def search(self, query: str, *, limit: int) -> Sequence[EvidenceCandidateDTO]: ...


class FileReaderPort(Protocol):
    """Bounded file reads, served by the repository context via a translator."""

    def read(self, path: str, start_line: int, end_line: int) -> str: ...


class CitationVerifierPort(Protocol):
    """Citation validity, served by the repository context via a translator."""

    def verify(self, path: str, start_line: int, end_line: int, commit_sha: str) -> bool: ...


class RunStorePort(Protocol):
    def save_report(self, report: ReportDTO) -> None: ...

    def load_report(self, run_id: RunId) -> ReportDTO | None: ...

    def list_recent(self, limit: int = 20) -> Sequence[ReportDTO]: ...
