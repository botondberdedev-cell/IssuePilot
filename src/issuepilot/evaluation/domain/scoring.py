"""Deterministic scoring.

Every metric here is a pure function of a case and a report — no model, no
network, no randomness — so a score is reproducible and a regression is
attributable. Model-assisted judging is deliberately absent: an uncalibrated
LLM judge as the only gate measures agreement with a model, not quality.

Metrics are expressed so that **higher is always better**, including the ones
counting bad things (they report the complement). A gate can then be a
uniform "at least this much" comparison rather than a per-metric direction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from issuepilot.evaluation.domain.case import EvaluationCase

_CITATION_RE: Final = re.compile(
    r"^(?P<path>.+?):(?P<start>\d+)-(?P<end>\d+) @ (?P<sha>[0-9a-f]+)$"
)


@dataclass(frozen=True, slots=True)
class ScoredReport:
    """The parts of a report scoring needs, decoupled from the report DTO so
    the evaluation context does not import the investigation context."""

    commit_sha: str
    completeness: str
    claims: tuple[str, ...]
    citations: tuple[str, ...]
    speculative_claims: tuple[str, ...]
    missing_information: tuple[str, ...]

    @property
    def is_complete(self) -> bool:
        return self.completeness == "complete"


@dataclass(frozen=True, slots=True)
class CaseScore:
    case_id: str
    category: str
    citation_validity: float
    """Fraction of citations that parse and name the run's own snapshot."""
    required_path_recall: float
    """Fraction of expected paths that were cited."""
    claim_grounding: float
    """Fraction of claims that are not bare speculation."""
    forbidden_claim_absence: float
    """1.0 when no forbidden substring appeared."""
    honesty: float
    """1.0 when a case expecting 'we cannot tell' got an incomplete answer."""

    @property
    def passed(self) -> bool:
        """A case passes only when nothing it guards against happened."""
        return (
            self.citation_validity == 1.0
            and self.required_path_recall == 1.0
            and self.forbidden_claim_absence == 1.0
            and self.honesty == 1.0
        )

    def as_dict(self) -> dict[str, float]:
        return {
            "citation-validity": self.citation_validity,
            "required-path-recall": self.required_path_recall,
            "claim-grounding": self.claim_grounding,
            "forbidden-claim-absence": self.forbidden_claim_absence,
            "honesty": self.honesty,
        }


def score_case(case: EvaluationCase, report: ScoredReport) -> CaseScore:
    return CaseScore(
        case_id=case.case_id,
        category=case.category.value,
        citation_validity=_citation_validity(report),
        required_path_recall=_required_path_recall(case, report),
        claim_grounding=_claim_grounding(report),
        forbidden_claim_absence=_forbidden_claim_absence(case, report),
        honesty=_honesty(case, report),
    )


def _citation_validity(report: ScoredReport) -> float:
    """A citation is valid when it parses and names this run's snapshot.

    No citations scores 1.0: there is nothing invalid. Whether the report
    *should* have cited something is required-path-recall's question.
    """
    if not report.citations:
        return 1.0
    valid = 0
    for citation in report.citations:
        match = _CITATION_RE.match(citation.strip())
        if match is None:
            continue
        if not report.commit_sha.startswith(match.group("sha")):
            continue
        if int(match.group("start")) > int(match.group("end")):
            continue
        valid += 1
    return valid / len(report.citations)


def _required_path_recall(case: EvaluationCase, report: ScoredReport) -> float:
    if not case.expected_paths:
        return 1.0
    cited_paths = {
        match.group("path")
        for citation in report.citations
        if (match := _CITATION_RE.match(citation.strip())) is not None
    }
    found = sum(1 for expected in case.expected_paths if _matches_any(expected, cited_paths))
    return found / len(case.expected_paths)


def _matches_any(expected: str, cited: set[str]) -> bool:
    """A suffix match, so a case can name ``refunds/webhook.py`` without
    pinning the fixture's directory layout."""
    return any(path == expected or path.endswith(f"/{expected}") for path in cited)


def _claim_grounding(report: ScoredReport) -> float:
    if not report.claims:
        return 1.0
    grounded = len(report.claims) - len(report.speculative_claims)
    return max(0.0, grounded / len(report.claims))


def _forbidden_claim_absence(case: EvaluationCase, report: ScoredReport) -> float:
    if not case.forbidden_claims:
        return 1.0
    haystack = " ".join(report.claims).lower()
    violations = sum(1 for phrase in case.forbidden_claims if phrase.lower() in haystack)
    return 0.0 if violations else 1.0


def _honesty(case: EvaluationCase, report: ScoredReport) -> float:
    """Saying 'the repository does not answer this' is a correct outcome.

    A case that expects it fails when the report instead asserts a confident,
    evidence-backed answer — which is precisely the invention this product
    exists to avoid.
    """
    if not case.expect_incomplete:
        return 1.0
    admitted = bool(report.missing_information) or not report.is_complete
    invented = any(claim not in report.speculative_claims for claim in report.claims)
    return 1.0 if admitted and not invented else 0.0


def aggregate(scores: list[CaseScore]) -> dict[str, float]:
    """Mean of each metric across cases. Empty input scores nothing rather
    than a misleading 1.0."""
    if not scores:
        return {}
    keys = scores[0].as_dict().keys()
    return {key: sum(score.as_dict()[key] for score in scores) / len(scores) for key in keys} | {
        "pass-rate": sum(1 for s in scores if s.passed) / len(scores)
    }
