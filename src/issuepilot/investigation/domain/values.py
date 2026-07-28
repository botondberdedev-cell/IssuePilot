"""Investigation-context value objects."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, unique
from typing import Final

_MAX_ISSUE_CHARS: Final = 100_000


@unique
class ToolName(StrEnum):
    """The closed set of tools an investigation strategy may request.

    Adding a member is a design decision (see governance tool policy), never
    a runtime extension — model output naming anything else is rejected.
    """

    REPOSITORY_MANIFEST = "repository_manifest"
    LIST_TREE = "list_tree"
    SEARCH_TEXT = "search_text"
    SEMANTIC_SEARCH = "semantic_search"
    READ_FILE = "read_file"
    RECORD_HYPOTHESIS = "record_hypothesis"
    FINISH = "finish"


@dataclass(frozen=True, slots=True)
class IssueStatement:
    """The problem or question to investigate, as provided by the user."""

    text: str

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("issue statement is empty")
        if len(self.text) > _MAX_ISSUE_CHARS:
            raise ValueError(
                f"issue statement exceeds {_MAX_ISSUE_CHARS} characters ({len(self.text)})"
            )

    @property
    def summary_line(self) -> str:
        first_line = self.text.strip().splitlines()[0]
        return first_line if len(first_line) <= 120 else first_line[:117] + "..."


@dataclass(frozen=True, slots=True)
class Confidence:
    """A calibrated confidence in [0, 1]."""

    value: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.value <= 1.0:
            raise ValueError(f"confidence must be within [0, 1], got {self.value}")
