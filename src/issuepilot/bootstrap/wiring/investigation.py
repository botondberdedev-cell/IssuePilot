"""Wires the investigation context and its translators to the other two.

Investigation declares what it needs — search, file reads, citation checks,
a reasoning model, prompts — and this module satisfies each from the
knowledge and repository facades. The three contexts remain unaware of one
another.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from typing import Any

from issuepilot.adapters.ollama.client import OllamaClient
from issuepilot.adapters.ollama.structured import StructuredGenerator
from issuepilot.investigation.application.dto import EvidenceCandidateDTO, ReportDTO
from issuepilot.investigation.application.ports import (
    RenderedPrompt,
    StructuredReply,
    StructuredRequest,
)
from issuepilot.investigation.application.public import InvestigationFacade
from issuepilot.investigation.application.strategies.react import ReActStrategy
from issuepilot.investigation.application.use_cases.run_investigation import RunInvestigation
from issuepilot.investigation.infrastructure.prompt_registry import PromptRegistry
from issuepilot.investigation.infrastructure.run_repo import SqliteRunStore
from issuepilot.knowledge.application.public import KnowledgeFacade
from issuepilot.repository.application.public import RepositoryFacade
from issuepilot.shared_kernel.clock import Clock
from issuepilot.shared_kernel.errors import PolicyDeniedError
from issuepilot.shared_kernel.events import EventBus
from issuepilot.shared_kernel.ids import IdGenerator


class OllamaReasoningModel:
    """Serves investigation's ReasoningModelPort from the structured generator."""

    def __init__(self, generator: StructuredGenerator) -> None:
        self._generator = generator

    def generate(self, request: StructuredRequest) -> StructuredReply:
        result = self._generator.generate(
            system=request.system, user=request.user, schema=dict(request.schema)
        )
        return StructuredReply(
            data=result.data,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            repairs=result.repairs,
        )


class RegistryPromptAdapter:
    """Serves investigation's PromptPort from the packaged prompt registry."""

    def __init__(self, registry: PromptRegistry) -> None:
        self._registry = registry

    def render(self, name: str, **context: Any) -> RenderedPrompt:
        prompt = self._registry.get(name)
        return RenderedPrompt(
            name=prompt.name,
            version=prompt.version,
            template_hash=prompt.template_hash,
            text=prompt.render(**context),
            schema=prompt.schema,
        )


class KnowledgeSearchTranslator:
    """Serves investigation's SearchPort from the knowledge facade."""

    def __init__(self, knowledge: KnowledgeFacade, commit_sha: str) -> None:
        self._knowledge = knowledge
        self._commit_sha = commit_sha

    def search(self, query: str, *, limit: int) -> Sequence[EvidenceCandidateDTO]:
        return tuple(
            EvidenceCandidateDTO(
                path=hit.path,
                start_line=hit.start_line,
                end_line=hit.end_line,
                snippet=hit.snippet,
                score=hit.score,
                commit_sha=hit.commit_sha,
                symbol=hit.symbol,
            )
            for hit in self._knowledge.search(self._commit_sha, query, limit=limit)
        )


class RepositoryReadTranslator:
    """Serves investigation's FileReaderPort and CitationVerifierPort.

    Both collapse failures into a benign result: a read that cannot happen
    raises, and a citation that cannot be confirmed is simply false. Neither
    ever surfaces content from outside the snapshot.
    """

    def __init__(self, repository: RepositoryFacade, root_path: str) -> None:
        self._repository = repository
        self._root_path = root_path

    def read(self, path: str, start_line: int, end_line: int) -> str:
        slice_ = self._repository.read_slice(self._root_path, "", path, start_line, end_line)
        return slice_.text

    def verify(self, path: str, start_line: int, end_line: int, commit_sha: str) -> bool:
        try:
            return self._repository.verify_citation(self._root_path, path, start_line, end_line)
        except PolicyDeniedError:
            return False


def build_investigation_facade(
    *,
    connection: sqlite3.Connection,
    repository: RepositoryFacade,
    knowledge: KnowledgeFacade,
    ids: IdGenerator,
    clock: Clock,
    bus: EventBus,
    ollama_url: str,
    chat_model: str,
    keep_alive: str,
    snapshot_roots: dict[str, str],
) -> InvestigationFacade:
    prompts = RegistryPromptAdapter(PromptRegistry())
    model = OllamaReasoningModel(
        StructuredGenerator(OllamaClient(ollama_url), chat_model, keep_alive=keep_alive)
    )
    store = SqliteRunStore(connection)

    def make_strategy(commit_sha: str) -> ReActStrategy:
        root = snapshot_roots.get(commit_sha, "")
        reads = RepositoryReadTranslator(repository, root)
        return ReActStrategy(
            model=model,
            prompts=prompts,
            search=KnowledgeSearchTranslator(knowledge, commit_sha),
            reader=reads,
            verifier=reads,
            commit_sha=commit_sha,
            file_count=len(repository.analyzable_paths(commit_sha)),
        )

    def verify(path: str, start_line: int, end_line: int, commit_sha: str) -> bool:
        root = snapshot_roots.get(commit_sha, "")
        return RepositoryReadTranslator(repository, root).verify(
            path, start_line, end_line, commit_sha
        )

    run = RunInvestigation(
        strategy_factory=make_strategy,
        model=model,
        prompts=prompts,
        verifier=_VerifierFn(verify),
        store=store,
        ids=ids,
        clock=clock,
        bus=bus,
    )
    return InvestigationFacade(run, store)


class _VerifierFn:
    """Adapts a plain function to CitationVerifierPort."""

    def __init__(self, fn: Any) -> None:
        self._fn = fn

    def verify(self, path: str, start_line: int, end_line: int, commit_sha: str) -> bool:
        verified: bool = self._fn(path, start_line, end_line, commit_sha)
        return verified


class InvestigationServiceAdapter:
    """Presents the investigation facade in the primitives the CLI speaks."""

    def __init__(
        self, facade: InvestigationFacade, snapshot_roots: dict[str, str], max_steps: int
    ) -> None:
        self._facade = facade
        self._snapshot_roots = snapshot_roots
        self._max_steps = max_steps

    def investigate(
        self,
        issue_text: str,
        commit_sha: str,
        root_path: str,
        *,
        max_steps: int | None = None,
        on_step: object = None,
    ) -> ReportDTO:
        self._snapshot_roots[commit_sha] = root_path
        return self._facade.investigate(
            issue_text,
            commit_sha,
            max_steps=max_steps or self._max_steps,
            on_step=on_step,
        )

    def recent_reports(self, limit: int = 20) -> Sequence[ReportDTO]:
        return self._facade.recent_reports(limit)

    def get_report(self, run_id: str) -> ReportDTO | None:
        return self._facade.get_report(run_id)
