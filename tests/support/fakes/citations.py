from __future__ import annotations


class FakeCitationVerifier:
    """Verifies membership in a pre-seeded set of (path, start, end, sha) tuples."""

    def __init__(self, valid: set[tuple[str, int, int, str]] | None = None) -> None:
        self._valid = valid or set()

    def allow(self, path: str, start_line: int, end_line: int, commit_sha: str) -> None:
        self._valid.add((path, start_line, end_line, commit_sha))

    def verify(self, path: str, start_line: int, end_line: int, commit_sha: str) -> bool:
        return (path, start_line, end_line, commit_sha) in self._valid
