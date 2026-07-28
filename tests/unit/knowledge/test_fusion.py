from __future__ import annotations

import pytest

from issuepilot.knowledge.domain.fusion import (
    RRF_K,
    FusedResult,
    diversify,
    reciprocal_rank_fusion,
)


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


class TestDiversify:
    def _results(self, *keys: str) -> list[FusedResult]:
        return reciprocal_rank_fusion({"lexical": list(keys)})

    def test_one_verbose_file_cannot_occupy_every_slot(self) -> None:
        """The failure this exists to prevent: a design document crowding out
        the code it describes."""
        fused = self._results("doc#1", "doc#2", "doc#3", "doc#4", "code#1")
        kept = diversify(fused, lambda r: r.key.split("#")[0], per_group=2, limit=3)
        assert [r.key for r in kept] == ["doc#1", "doc#2", "code#1"]

    def test_rank_order_is_preserved_within_the_cap(self) -> None:
        fused = self._results("a#1", "b#1", "a#2", "b#2")
        kept = diversify(fused, lambda r: r.key.split("#")[0], per_group=2)
        assert [r.key for r in kept][:4] == ["a#1", "b#1", "a#2", "b#2"]

    def test_overflow_is_appended_not_discarded(self) -> None:
        """A genuinely one-file answer still surfaces the rest of that file."""
        fused = self._results("a#1", "a#2", "a#3")
        kept = diversify(fused, lambda r: r.key.split("#")[0], per_group=1)
        assert [r.key for r in kept] == ["a#1", "a#2", "a#3"]

    def test_limit_truncates_after_diversifying(self) -> None:
        fused = self._results("a#1", "a#2", "b#1")
        kept = diversify(fused, lambda r: r.key.split("#")[0], per_group=1, limit=2)
        assert [r.key for r in kept] == ["a#1", "b#1"]

    def test_empty_input_yields_empty(self) -> None:
        assert diversify([], lambda r: r.key) == []

    def test_a_nonpositive_cap_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="per_group must be positive"):
            diversify(self._results("a#1"), lambda r: r.key, per_group=0)
