"""Contract suite for investigation's SearchPort."""

from __future__ import annotations

import pytest

from issuepilot.investigation.application.dto import EvidenceCandidateDTO
from issuepilot.investigation.application.ports import SearchPort
from tests.support.fakes.investigation import FakeSearch

SHA = "c" * 40


def candidate(path: str, score: float) -> EvidenceCandidateDTO:
    return EvidenceCandidateDTO(
        path=path, start_line=1, end_line=5, snippet="...", score=score, commit_sha=SHA
    )


@pytest.fixture(params=["fake"])
def search(request: pytest.FixtureRequest) -> SearchPort:
    return FakeSearch(
        [candidate("low.py", 0.1), candidate("high.py", 0.9), candidate("mid.py", 0.5)]
    )


def test_results_are_sorted_by_score_descending(search: SearchPort) -> None:
    scores = [c.score for c in search.search("anything", limit=10)]
    assert scores == sorted(scores, reverse=True)


def test_limit_is_respected(search: SearchPort) -> None:
    assert len(search.search("anything", limit=2)) == 2


def test_hits_carry_citable_coordinates(search: SearchPort) -> None:
    for hit in search.search("anything", limit=10):
        assert hit.path
        assert 1 <= hit.start_line <= hit.end_line
        assert hit.commit_sha


def test_empty_index_returns_empty() -> None:
    assert list(FakeSearch().search("anything", limit=5)) == []
