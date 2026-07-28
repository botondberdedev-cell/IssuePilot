from __future__ import annotations

import pytest

from issuepilot.knowledge.domain.values import Query, RetrievalScore


def test_query_must_have_content() -> None:
    with pytest.raises(ValueError, match="empty"):
        Query("   ")
    assert Query("where is auth enforced").text


def test_score_must_be_non_negative() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        RetrievalScore(-0.1)
    assert RetrievalScore(0.0).value == 0.0
