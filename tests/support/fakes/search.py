from __future__ import annotations

from collections.abc import Sequence

from issuepilot.investigation.application.dto import EvidenceCandidateDTO


class FakeSearch:
    """Returns pre-seeded candidates, highest score first, respecting the limit."""

    def __init__(self, candidates: Sequence[EvidenceCandidateDTO] = ()) -> None:
        self._candidates = list(candidates)
        self.queries: list[str] = []

    def search(self, query: str, *, limit: int) -> Sequence[EvidenceCandidateDTO]:
        self.queries.append(query)
        ranked = sorted(self._candidates, key=lambda c: c.score, reverse=True)
        return ranked[:limit]
