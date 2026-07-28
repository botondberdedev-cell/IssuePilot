"""Reciprocal rank fusion.

Lexical and semantic scores are not comparable — BM25 is unbounded, cosine
similarity sits in [-1, 1] — so blending them numerically produces a number
nobody can interpret or tune. RRF instead combines *ranks*, which are
comparable by construction, and the per-source ranks are preserved on the
result so evaluation can attribute a hit to the retriever that found it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final

RRF_K: Final = 60
"""Damping constant from the original RRF paper: large enough that the top
few ranks do not dominate, small enough that deep ranks still matter."""


@dataclass(frozen=True, slots=True)
class FusedResult:
    key: str
    score: float
    ranks: Mapping[str, int] = field(default_factory=dict)
    """Per-source 1-based rank, for explaining and evaluating a result."""

    @property
    def sources(self) -> tuple[str, ...]:
        return tuple(sorted(self.ranks))


def reciprocal_rank_fusion(
    ranked_lists: Mapping[str, Sequence[str]], *, k: int = RRF_K, limit: int | None = None
) -> list[FusedResult]:
    """Fuse ranked key lists into one ranking.

    Ties break on the fused score first, then on the best rank achieved in
    any source, then on the key — so the output is fully deterministic rather
    than dependent on dictionary iteration order.
    """
    if k < 1:
        raise ValueError(f"RRF k must be positive, got {k}")

    scores: dict[str, float] = {}
    ranks: dict[str, dict[str, int]] = {}
    for source, keys in ranked_lists.items():
        for position, key in enumerate(keys, start=1):
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + position)
            ranks.setdefault(key, {})[source] = position

    fused = [FusedResult(key=key, score=score, ranks=ranks[key]) for key, score in scores.items()]
    fused.sort(key=lambda r: (-r.score, min(r.ranks.values()), r.key))
    return fused[:limit] if limit is not None else fused
