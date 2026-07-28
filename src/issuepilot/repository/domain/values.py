"""Repository-context value objects.

``RepositoryLocator`` is a security boundary: every accepted form is an
explicit decision, and everything else is rejected at construction time.
See the threat model — argv injection (leading ``-``), ``ext::``/remote
helpers, embedded credentials, and control characters are all blocked here,
before any git process exists.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, unique
from typing import Final

_SHA_RE: Final = re.compile(r"^[0-9a-f]{40}$")
_HTTPS_RE: Final = re.compile(r"^https://[^@/\s]+(:\d+)?/\S+$")
_SSH_URL_RE: Final = re.compile(r"^ssh://([^@\s/]+@)?[^@/\s]+(:\d+)?/\S+$")
# SCP-like syntax: git@host:owner/repo.git — host contains no '/' or ':'
_SCP_LIKE_RE: Final = re.compile(r"^([^@\s/:]+@)?[^@/\s:]+:(?!//)[^:\s]+$")
_CONTROL_CHARS: Final = re.compile(r"[\x00-\x1f\x7f]")


@unique
class LocatorKind(Enum):
    HTTPS = "https"
    SSH = "ssh"
    LOCAL_PATH = "local-path"


@dataclass(frozen=True, slots=True)
class RepositoryLocator:
    """A validated repository location. Use :meth:`parse` — never the raw ctor."""

    raw: str
    kind: LocatorKind

    @classmethod
    def parse(cls, raw: str, *, allow_local_path: bool = False) -> RepositoryLocator:
        candidate = raw.strip()
        if not candidate:
            raise ValueError("repository locator is empty")
        if _CONTROL_CHARS.search(candidate):
            raise ValueError("repository locator contains control characters")
        if candidate.startswith("-"):
            raise ValueError("repository locator may not begin with '-'")

        lowered = candidate.lower()
        for forbidden, why in (
            ("git://", "no authentication or transport security"),
            ("ftp://", "insecure transport"),
            ("ftps://", "unsupported transport"),
            ("ext::", "arbitrary command execution via remote helper"),
            ("file://", "use --allow-local-path with a plain path instead"),
        ):
            if lowered.startswith(forbidden):
                raise ValueError(f"transport not allowed ({forbidden.rstrip(':/')}): {why}")

        if lowered.startswith("https://"):
            if "@" in candidate.split("://", 1)[1].split("/", 1)[0]:
                raise ValueError(
                    "embedded credentials in HTTPS locators are not allowed; "
                    "use git's credential helper"
                )
            if not _HTTPS_RE.match(candidate):
                raise ValueError("malformed https locator")
            return cls(candidate, LocatorKind.HTTPS)

        if lowered.startswith("ssh://"):
            if not _SSH_URL_RE.match(candidate):
                raise ValueError("malformed ssh locator")
            return cls(candidate, LocatorKind.SSH)

        if lowered.startswith("http://"):
            raise ValueError("plain http is not allowed; use https")

        if candidate.startswith(("/", "~")):
            if not allow_local_path:
                raise ValueError("local paths require --allow-local-path")
            return cls(candidate, LocatorKind.LOCAL_PATH)

        if _SCP_LIKE_RE.match(candidate):
            return cls(candidate, LocatorKind.SSH)

        raise ValueError(
            "unrecognized repository locator; expected https://, ssh://, "
            "user@host:path, or an absolute path with --allow-local-path"
        )


@dataclass(frozen=True, slots=True)
class RepositoryRef:
    """A branch, tag, or commit reference as requested by the user."""

    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise ValueError("repository ref is empty")
        if self.value.startswith("-"):
            raise ValueError("repository ref may not begin with '-'")
        if _CONTROL_CHARS.search(self.value):
            raise ValueError("repository ref contains control characters")
        if any(seq in self.value for seq in ("..", "//", "\\")) or self.value.endswith("."):
            raise ValueError(f"malformed repository ref: {self.value!r}")


@dataclass(frozen=True, slots=True)
class CommitSha:
    """A fully resolved 40-hex-digit commit SHA. Never abbreviated."""

    value: str

    def __post_init__(self) -> None:
        if not _SHA_RE.match(self.value):
            raise ValueError(f"not a full lowercase commit sha: {self.value!r}")

    @property
    def short(self) -> str:
        return self.value[:12]


@dataclass(frozen=True, slots=True)
class RelativeRepoPath:
    """A path inside a snapshot. Guaranteed relative and traversal-free."""

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("repository path is empty")
        if "\x00" in self.value:
            raise ValueError("repository path contains NUL")
        if self.value.startswith(("/", "~")) or (len(self.value) > 1 and self.value[1] == ":"):
            raise ValueError(f"repository path must be relative: {self.value!r}")
        parts = self.value.split("/")
        if any(part in ("", ".", "..") for part in parts):
            raise ValueError(f"repository path must be normalized: {self.value!r}")


@dataclass(frozen=True, slots=True)
class LineRange:
    """Inclusive 1-based line range."""

    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 1:
            raise ValueError(f"line range must start at 1 or later, got {self.start}")
        if self.end < self.start:
            raise ValueError(f"line range end {self.end} precedes start {self.start}")

    @property
    def line_count(self) -> int:
        return self.end - self.start + 1
