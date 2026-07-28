"""Contract suite for SearchPort (knowledge-context translator joins in v0.1)."""

from __future__ import annotations

import pytest

from issuepilot.investigation.application.dto import EvidenceCandidateDTO
from issuepilot.investigation.application.ports import SearchPort
from tests.support.fakes.search import FakeSearch

SHA = "c" * 40


def _candidate(path: str, score: float) -> EvidenceCandidateDTO:
    return EvidenceCandidateDTO(
        path=path, start_line=1, end_line=5, snippet="...", score=score, commit_sha=SHA
    )


@pytest.fixture(params=["fake"])
def search(request: pytest.FixtureRequest) -> SearchPort:
    return FakeSearch(
        [_candidate("low.py", 0.1), _candidate("high.py", 0.9), _candidate("mid.py", 0.5)]
    )


def test_results_are_sorted_by_score_descending(search: SearchPort) -> None:
    results = search.search("anything", limit=10)
    scores = [c.score for c in results]
    assert scores == sorted(scores, reverse=True)


def test_limit_is_respected(search: SearchPort) -> None:
    assert len(search.search("anything", limit=2)) == 2


def test_empty_index_returns_empty() -> None:
    assert list(FakeSearch().search("anything", limit=5)) == []
