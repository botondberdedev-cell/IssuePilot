"""One step of an investigation: the action taken and what it revealed.

Only the model's *chosen action* and a short user-facing reason are kept —
never unrestricted private reasoning. The observation is truncated on the way
in, so a single enormous tool result cannot dominate the next prompt or the
stored run.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from issuepilot.investigation.domain.values import ToolName

MAX_OBSERVATION_CHARS: Final = 4_000


@dataclass(frozen=True, slots=True)
class ToolCall:
    tool: ToolName
    query: str | None = None
    path: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    hypothesis: str | None = None

    def describe(self) -> str:
        """A short human-readable form, used in progress output and prompts."""
        if self.tool in (ToolName.SEARCH_TEXT, ToolName.SEMANTIC_SEARCH):
            return f"{self.tool.value}({self.query!r})"
        if self.tool is ToolName.READ_FILE:
            span = (
                f":{self.start_line}-{self.end_line}"
                if self.start_line is not None and self.end_line is not None
                else ""
            )
            return f"read_file({self.path}{span})"
        if self.tool is ToolName.RECORD_HYPOTHESIS:
            return "record_hypothesis(...)"
        return self.tool.value


@dataclass(frozen=True, slots=True)
class Step:
    index: int
    call: ToolCall
    reason: str
    observation: str

    def __post_init__(self) -> None:
        if self.index < 1:
            raise ValueError(f"step index starts at 1, got {self.index}")
        if len(self.observation) > MAX_OBSERVATION_CHARS:
            object.__setattr__(
                self,
                "observation",
                self.observation[:MAX_OBSERVATION_CHARS] + "\n… (truncated)",
            )

    @property
    def tool(self) -> str:
        return self.call.tool.value
