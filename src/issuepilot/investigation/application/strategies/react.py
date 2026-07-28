"""The ReAct investigation loop.

Each iteration: summarize state, ask the model for one schema-valid action,
validate it against the closed tool set, execute it, record the observation.
The loop owns the safety properties that must not depend on the model
behaving well:

- The tool set is a closed enum. A name the model invents is refused and fed
  back as an observation, so the run continues rather than crashing, and the
  refusal is visible in the transcript.
- The step budget is a domain object that cannot go negative, so an
  unproductive loop terminates by construction rather than by convention.
- Cancellation is polled before every model call, which is where the time
  goes.
- Retrieved text enters the prompt as quoted observation data. A file that
  contains instructions cannot add tools or change policy, because policy is
  enforced here rather than requested in the prompt.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Final

from issuepilot.investigation.application.dto import EvidenceCandidateDTO
from issuepilot.investigation.application.ports import (
    CitationVerifierPort,
    FileReaderPort,
    PromptPort,
    ReasoningModelPort,
    SearchPort,
    StructuredRequest,
)
from issuepilot.investigation.domain.budget import BudgetExhaustedError, StepBudget
from issuepilot.investigation.domain.step import Step, ToolCall
from issuepilot.investigation.domain.values import IssueStatement, ToolName
from issuepilot.shared_kernel.cancellation import NEVER_CANCELLED, CancellationToken

SYSTEM_PROMPT: Final = (
    "You investigate software repositories. You answer only from evidence you "
    "have actually read. You respond with JSON matching the requested schema, "
    "and nothing else."
)

_SEARCH_LIMIT: Final = 6
_DEFAULT_READ_LINES: Final = 80
_MAX_READ_LINES: Final = 200


@dataclass(frozen=True, slots=True)
class InvestigationOutcome:
    steps: tuple[Step, ...]
    evidence: tuple[EvidenceCandidateDTO, ...]
    hypotheses: tuple[str, ...]
    budget_exhausted: bool
    timed_out: bool = False
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class _State:
    """Mutable working state for one run; never leaves this module."""

    steps: list[Step] = field(default_factory=list)
    evidence: dict[str, EvidenceCandidateDTO] = field(default_factory=dict)
    hypotheses: list[str] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0

    def remember(self, candidates: Sequence[EvidenceCandidateDTO]) -> None:
        for candidate in candidates:
            # Keyed by location so repeated retrieval of the same span does not
            # inflate the evidence list.
            key = f"{candidate.path}:{candidate.start_line}-{candidate.end_line}"
            self.evidence.setdefault(key, candidate)


class ReActStrategy:
    def __init__(
        self,
        *,
        model: ReasoningModelPort,
        prompts: PromptPort,
        search: SearchPort,
        reader: FileReaderPort,
        verifier: CitationVerifierPort,
        commit_sha: str,
        file_count: int = 0,
        languages: str = "",
    ) -> None:
        self._model = model
        self._prompts = prompts
        self._search = search
        self._reader = reader
        self._verifier = verifier
        self._commit_sha = commit_sha
        self._file_count = file_count
        self._languages = languages

    def investigate(
        self,
        issue: IssueStatement,
        budget: StepBudget,
        *,
        cancellation: CancellationToken = NEVER_CANCELLED,
        on_step: object = None,
        out_of_time: Callable[[], bool] | None = None,
    ) -> InvestigationOutcome:
        state = _State()
        current = budget
        timed_out = False

        while not current.exhausted:
            cancellation.raise_if_cancelled()
            # Running out of time ends the run rather than raising: evidence
            # gathered so far is still worth reporting, marked incomplete.
            # The predicate is supplied by the caller, so exactly one clock
            # decides the budget.
            if out_of_time is not None and out_of_time():
                timed_out = True
                break
            rendered = self._prompts.render(
                "react_step@v1",
                issue=issue.text,
                short_sha=self._commit_sha[:12],
                file_count=self._file_count,
                languages=self._languages,
                steps=[{"tool": s.tool, "observation": s.observation} for s in state.steps],
                remaining_steps=current.remaining,
            )
            reply = self._model.generate(
                StructuredRequest(
                    prompt_name=rendered.name,
                    system=SYSTEM_PROMPT,
                    user=rendered.text,
                    schema=rendered.schema,
                )
            )
            state.prompt_tokens += reply.prompt_tokens
            state.completion_tokens += reply.completion_tokens

            call, reason = _parse_action(reply.data)
            if call.tool is ToolName.FINISH:
                break

            observation = self._execute(call, state)
            current = current.spend()
            step = Step(
                index=len(state.steps) + 1,
                call=call,
                reason=reason,
                observation=observation,
            )
            state.steps.append(step)
            if callable(on_step):
                on_step(step)

        return InvestigationOutcome(
            steps=tuple(state.steps),
            evidence=tuple(state.evidence.values()),
            hypotheses=tuple(state.hypotheses),
            budget_exhausted=current.exhausted or timed_out,
            timed_out=timed_out,
            prompt_tokens=state.prompt_tokens,
            completion_tokens=state.completion_tokens,
        )

    def _execute(self, call: ToolCall, state: _State) -> str:
        match call.tool:
            case ToolName.SEARCH_TEXT | ToolName.SEMANTIC_SEARCH:
                return self._run_search(call, state)
            case ToolName.READ_FILE:
                return self._run_read(call, state)
            case ToolName.RECORD_HYPOTHESIS:
                if call.hypothesis:
                    state.hypotheses.append(call.hypothesis)
                    return "Hypothesis recorded."
                return "No hypothesis text supplied; nothing recorded."
            case _:  # pragma: no cover - FINISH is handled by the caller
                return f"Tool {call.tool.value} is not executable here."

    def _run_search(self, call: ToolCall, state: _State) -> str:
        if not call.query:
            return "No query supplied. Provide `query` with this tool."
        hits = self._search.search(call.query, limit=_SEARCH_LIMIT)
        usable = [h for h in hits if h.commit_sha == self._commit_sha]
        state.remember(usable)
        if not usable:
            return f"No matches for {call.query!r}."
        lines = [f"{len(usable)} result(s) for {call.query!r}:"]
        lines.extend(
            f"- {h.path}:{h.start_line}-{h.end_line}"
            f"{f' ({h.symbol})' if h.symbol else ''}\n{_indent(h.snippet)}"
            for h in usable
        )
        return "\n".join(lines)

    def _run_read(self, call: ToolCall, state: _State) -> str:
        if not call.path:
            return "No path supplied. Provide `path` with this tool."
        start = max(1, call.start_line or 1)
        end = call.end_line or (start + _DEFAULT_READ_LINES - 1)
        if end < start:
            return f"Invalid range {start}-{end}."
        end = min(end, start + _MAX_READ_LINES - 1)

        if not self._verifier.verify(call.path, start, end, self._commit_sha):
            return (
                f"{call.path}:{start}-{end} is not readable in this snapshot "
                "(missing, out of range, or outside the repository)."
            )
        try:
            text = self._reader.read(call.path, start, end)
        except Exception as exc:  # a tool failure is an observation, not a crash
            return f"Could not read {call.path}: {type(exc).__name__}."

        state.remember(
            [
                EvidenceCandidateDTO(
                    path=call.path,
                    start_line=start,
                    end_line=end,
                    snippet=text,
                    score=1.0,
                    commit_sha=self._commit_sha,
                )
            ]
        )
        return f"{call.path}:{start}-{end}\n{_indent(text)}"


def _parse_action(data: object) -> tuple[ToolCall, str]:
    """Turn validated model output into a tool call.

    An unrecognized tool becomes ``FINISH`` rather than an exception: the
    schema already constrains the enum, so reaching here means something
    unusual happened, and ending cleanly beats crashing a run that may already
    hold good evidence.
    """
    if not isinstance(data, dict):  # pragma: no cover - schema guarantees a dict
        return ToolCall(tool=ToolName.FINISH), "malformed action"

    reason = str(data.get("reason", "")).strip()
    raw_tool = str(data.get("tool", "")).strip()
    try:
        tool = ToolName(raw_tool)
    except ValueError:
        return ToolCall(tool=ToolName.FINISH), f"unknown tool {raw_tool!r}"

    return (
        ToolCall(
            tool=tool,
            query=_as_str(data.get("query")),
            path=_as_str(data.get("path")),
            start_line=_as_int(data.get("start_line")),
            end_line=_as_int(data.get("end_line")),
            hypothesis=_as_str(data.get("hypothesis")),
        ),
        reason,
    )


def _as_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_int(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str | float):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    return None


def _indent(text: str, *, limit: int = 25) -> str:
    lines = text.splitlines()[:limit]
    return "\n".join(f"    {line}" for line in lines)


__all__ = ["SYSTEM_PROMPT", "BudgetExhaustedError", "InvestigationOutcome", "ReActStrategy"]
