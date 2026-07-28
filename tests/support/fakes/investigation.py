"""Fakes for the investigation context's ports."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from issuepilot.investigation.application.dto import EvidenceCandidateDTO, ReportDTO
from issuepilot.investigation.application.ports import (
    RenderedPrompt,
    StructuredReply,
    StructuredRequest,
)
from issuepilot.shared_kernel.ids import RunId


class ScriptedReasoningModel:
    """Replays a scripted sequence of structured replies.

    Scripting the model is what makes an agent loop testable: the same
    transcript produces the same run, so a test can assert on control flow
    rather than on whatever a model happened to say.
    """

    def __init__(self, replies: Sequence[dict[str, Any]] | None = None) -> None:
        self._replies = list(replies or [])
        self.requests: list[StructuredRequest] = []

    def generate(self, request: StructuredRequest) -> StructuredReply:
        self.requests.append(request)
        if not self._replies:
            raise RuntimeError("ScriptedReasoningModel ran out of replies")
        return StructuredReply(data=self._replies.pop(0), prompt_tokens=10, completion_tokens=5)

    @property
    def prompts_seen(self) -> list[str]:
        return [r.prompt_name for r in self.requests]


class FakePrompts:
    """Renders a trivially inspectable prompt, so tests can assert on the
    context passed in rather than on template formatting."""

    def __init__(self) -> None:
        self.rendered: list[tuple[str, dict[str, Any]]] = []

    def render(self, name: str, **context: Any) -> RenderedPrompt:
        self.rendered.append((name, context))
        body = "\n".join(f"{key}={value!r}" for key, value in sorted(context.items()))
        return RenderedPrompt(
            name=name,
            version="1.0.0",
            template_hash="fake",
            text=f"[{name}]\n{body}",
            schema={"type": "object"},
        )

    def context_for(self, name: str) -> dict[str, Any]:
        for rendered_name, context in reversed(self.rendered):
            if rendered_name == name:
                return context
        raise AssertionError(f"prompt {name!r} was never rendered")


class FakeSearch:
    def __init__(self, candidates: Sequence[EvidenceCandidateDTO] = ()) -> None:
        self._candidates = list(candidates)
        self.queries: list[str] = []

    def search(self, query: str, *, limit: int) -> Sequence[EvidenceCandidateDTO]:
        self.queries.append(query)
        ranked = sorted(self._candidates, key=lambda c: c.score, reverse=True)
        return tuple(ranked[:limit])


class FakeFileReader:
    def __init__(self, files: dict[str, str] | None = None) -> None:
        self._files = files or {}
        self.reads: list[tuple[str, int, int]] = []

    def add(self, path: str, text: str) -> None:
        self._files[path] = text

    def read(self, path: str, start_line: int, end_line: int) -> str:
        self.reads.append((path, start_line, end_line))
        if path not in self._files:
            raise FileNotFoundError(path)
        lines = self._files[path].splitlines(keepends=True)
        return "".join(lines[start_line - 1 : end_line])


class FakeCitationVerifier:
    def __init__(self, valid: set[tuple[str, int, int, str]] | None = None) -> None:
        self._valid = valid or set()
        self.allow_all = False

    def allow(self, path: str, start_line: int, end_line: int, commit_sha: str) -> None:
        self._valid.add((path, start_line, end_line, commit_sha))

    def verify(self, path: str, start_line: int, end_line: int, commit_sha: str) -> bool:
        if self.allow_all:
            return True
        return (path, start_line, end_line, commit_sha) in self._valid


class InMemoryRunStore:
    def __init__(self) -> None:
        self._reports: dict[str, ReportDTO] = {}

    def save_report(self, report: ReportDTO) -> None:
        self._reports[report.run_id] = report

    def load_report(self, run_id: RunId) -> ReportDTO | None:
        return self._reports.get(run_id)

    def list_recent(self, limit: int = 20) -> Sequence[ReportDTO]:
        ordered = sorted(self._reports.values(), key=lambda r: r.run_id, reverse=True)
        return tuple(ordered[:limit])
