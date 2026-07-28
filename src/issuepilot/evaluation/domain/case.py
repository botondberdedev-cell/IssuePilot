"""Evaluation cases: labelled inputs with expected properties.

A case says what a good answer *contains*, not what it says. Expecting exact
prose from a language model produces a brittle suite that fails on harmless
rewording; expecting the right files to be cited, and the wrong claims to be
absent, tests what actually matters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum, unique

from issuepilot.shared_kernel.ids import EvalCaseId


@unique
class CaseCategory(StrEnum):
    """What a case is designed to probe. Kept explicit so a suite can report
    where quality is concentrated rather than a single average."""

    BUG_LOCATION = "bug-location"
    CROSS_MODULE = "cross-module"
    CONFIGURATION = "configuration"
    ARCHITECTURE = "architecture"
    MISSING_INFORMATION = "missing-information"
    """The repository does not contain the answer; the right result is to say so."""
    MISLEADING_ISSUE = "misleading-issue"
    PROMPT_INJECTION = "prompt-injection"
    """A file tries to instruct the agent; it must report rather than obey."""


@unique
class Difficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    case_id: EvalCaseId
    issue: str
    category: CaseCategory
    fixture: str
    """Name of the fixture repository this case runs against."""
    expected_paths: tuple[str, ...] = ()
    """Files a good answer must cite at least one of, per path."""
    forbidden_claims: tuple[str, ...] = ()
    """Substrings that must NOT appear — hallucinations this case guards."""
    expect_incomplete: bool = False
    """True when the honest answer is 'the repository does not say'."""
    difficulty: Difficulty = Difficulty.MEDIUM
    tags: tuple[str, ...] = field(default=())

    def __post_init__(self) -> None:
        if not self.issue.strip():
            raise ValueError(f"case {self.case_id} has no issue text")
        if not self.fixture.strip():
            raise ValueError(f"case {self.case_id} names no fixture")
        if self.expect_incomplete and self.expected_paths:
            raise ValueError(
                f"case {self.case_id} expects an incomplete answer but also "
                "requires cited paths; it cannot be both"
            )
        if not self.expect_incomplete and not self.expected_paths:
            raise ValueError(
                f"case {self.case_id} requires no paths and expects a complete "
                "answer, so nothing would be checked"
            )


@dataclass(frozen=True, slots=True)
class EvaluationDataset:
    version: str
    cases: tuple[EvaluationCase, ...]

    def __post_init__(self) -> None:
        if not self.version.strip():
            raise ValueError("a dataset requires a version")
        seen = [c.case_id for c in self.cases]
        duplicates = {cid for cid in seen if seen.count(cid) > 1}
        if duplicates:
            raise ValueError(f"duplicate case ids: {sorted(duplicates)}")

    def __len__(self) -> int:
        return len(self.cases)

    def by_category(self, category: CaseCategory) -> tuple[EvaluationCase, ...]:
        return tuple(c for c in self.cases if c.category is category)

    def category_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for case in self.cases:
            counts[case.category.value] = counts.get(case.category.value, 0) + 1
        return dict(sorted(counts.items()))
