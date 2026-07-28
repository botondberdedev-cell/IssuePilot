"""Knowledge-context domain events."""

from __future__ import annotations

from dataclasses import dataclass

from issuepilot.shared_kernel.events import DomainEvent


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeIndexReady(DomainEvent):
    index_id: str
    snapshot_sha: str
    chunk_count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class KnowledgeIndexFailed(DomainEvent):
    snapshot_sha: str
    reason_category: str
