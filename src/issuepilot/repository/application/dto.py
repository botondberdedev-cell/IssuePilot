"""Immutable DTOs crossing the repository context's boundary."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class SnapshotDTO:
    snapshot_id: str
    commit_sha: str
    requested_ref: str
    locator_fingerprint: str
    root_path: str
    reused_cache: bool = False


@dataclass(frozen=True, slots=True)
class ManifestDTO:
    commit_sha: str
    requested_ref: str
    included_count: int
    excluded_count: int
    total_bytes: int
    languages: Mapping[str, int]
    exclusions: Mapping[str, int]
    sample_paths: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "languages", MappingProxyType(dict(self.languages)))
        object.__setattr__(self, "exclusions", MappingProxyType(dict(self.exclusions)))


@dataclass(frozen=True, slots=True)
class FileSliceDTO:
    path: str
    start_line: int
    end_line: int
    commit_sha: str
    text: str
