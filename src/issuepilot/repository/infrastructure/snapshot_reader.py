"""Bounded, confined reads from a materialized snapshot.

Every entry point resolves the path through ``resolve_within``, so untrusted
repository content cannot direct a read outside the snapshot. Reads are
streamed line by line and stop at the requested range, so a citation into a
very large file costs the range, not the file.
"""

from __future__ import annotations

from pathlib import Path

from issuepilot.repository.domain.values import LineRange, RelativeRepoPath
from issuepilot.repository.infrastructure.workspace import resolve_within
from issuepilot.shared_kernel.errors import PolicyDeniedError


class SnapshotReader:
    def contains(self, root_path: str, path: RelativeRepoPath) -> bool:
        try:
            resolved = resolve_within(Path(root_path), path.value)
        except PolicyDeniedError:
            return False
        return resolved.is_file()

    def line_count(self, root_path: str, path: RelativeRepoPath) -> int:
        resolved = self._readable(root_path, path)
        with resolved.open("r", encoding="utf-8", errors="replace") as handle:
            return sum(1 for _ in handle)

    def read_slice(self, root_path: str, path: RelativeRepoPath, line_range: LineRange) -> str:
        resolved = self._readable(root_path, path)
        collected: list[str] = []
        with resolved.open("r", encoding="utf-8", errors="replace") as handle:
            for number, line in enumerate(handle, start=1):
                if number > line_range.end:
                    break
                if number >= line_range.start:
                    collected.append(line)
        return "".join(collected)

    def _readable(self, root_path: str, path: RelativeRepoPath) -> Path:
        resolved = resolve_within(Path(root_path), path.value)
        if not resolved.is_file():
            raise FileNotFoundError(f"{path.value} is not a file in this snapshot")
        return resolved
