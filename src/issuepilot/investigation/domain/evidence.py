"""Evidence: the atomic proof unit of an investigation.

The investigation context deliberately defines its own path/sha validation
(contexts are independent); the constraints mirror the repository context's.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

_SHA_RE: Final = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    """An exact location in the investigated snapshot: path, lines, commit."""

    path: str
    start_line: int
    end_line: int
    commit_sha: str

    def __post_init__(self) -> None:
        if not self.path or "\x00" in self.path:
            raise ValueError("evidence path is empty or malformed")
        if self.path.startswith(("/", "~")):
            raise ValueError(f"evidence path must be relative: {self.path!r}")
        if any(part in ("", ".", "..") for part in self.path.split("/")):
            raise ValueError(f"evidence path must be normalized: {self.path!r}")
        if self.start_line < 1 or self.end_line < self.start_line:
            raise ValueError(f"invalid evidence line range {self.start_line}-{self.end_line}")
        if not _SHA_RE.match(self.commit_sha):
            raise ValueError(f"evidence requires a full commit sha, got {self.commit_sha!r}")

    def cite(self) -> str:
        """ASCII-only citation form: ``path:start-end @ shortsha``."""
        return f"{self.path}:{self.start_line}-{self.end_line} @ {self.commit_sha[:12]}"
