from __future__ import annotations

import pytest

from issuepilot.knowledge.domain.fusion import RRF_K, reciprocal_rank_fusion


def test_single_source_preserves_its_order() -> None:
    fused = reciprocal_rank_fusion({"lexical": ["a", "b", "c"]})
    assert [r.key for r in fused] == ["a", "b", "c"]


def test_agreement_between_sources_outranks_a_single_top_hit() -> None:
    """Something both retrievers like beats something only one ranks first."""
    fused = reciprocal_rank_fusion(
        {"lexical": ["only_lexical", "agreed"], "semantic": ["agreed", "only_semantic"]}
    )
    assert fused[0].key == "agreed"


def test_per_source_ranks_are_preserved() -> None:
    fused = reciprocal_rank_fusion({"lexical": ["x", "y"], "semantic": ["y", "x"]})
    by_key = {r.key: r for r in fused}
    assert by_key["x"].ranks == {"lexical": 1, "semantic": 2}
    assert by_key["y"].ranks == {"lexical": 2, "semantic": 1}
    assert by_key["x"].sources == ("lexical", "semantic")


def test_score_matches_the_rrf_formula() -> None:
    (result,) = reciprocal_rank_fusion({"lexical": ["a"]})
    assert result.score == pytest.approx(1.0 / (RRF_K + 1))


def test_result_is_deterministic_regardless_of_source_order() -> None:
    first = reciprocal_rank_fusion({"a": ["x", "y"], "b": ["y", "x"]})
    second = reciprocal_rank_fusion({"b": ["y", "x"], "a": ["x", "y"]})
    assert [r.key for r in first] == [r.key for r in second]


def test_ties_break_deterministically_by_key() -> None:
    fused = reciprocal_rank_fusion({"lexical": ["b"], "semantic": ["a"]})
    assert [r.key for r in fused] == ["a", "b"]


def test_limit_truncates() -> None:
    fused = reciprocal_rank_fusion({"lexical": ["a", "b", "c", "d"]}, limit=2)
    assert len(fused) == 2


def test_scores_decrease_monotonically_with_rank() -> None:
    fused = reciprocal_rank_fusion({"lexical": ["a", "b", "c", "d", "e"]})
    scores = [r.score for r in fused]
    assert scores == sorted(scores, reverse=True)


def test_empty_input_yields_empty_output() -> None:
    assert reciprocal_rank_fusion({}) == []
    assert reciprocal_rank_fusion({"lexical": []}) == []


def test_invalid_k_is_rejected() -> None:
    with pytest.raises(ValueError, match="k must be positive"):
        reciprocal_rank_fusion({"lexical": ["a"]}, k=0)
