"""What a snapshot contains, and which files are eligible for analysis.

The eligibility policy is a pure function of a path, its size, and whether
Git considers it binary — no filesystem access — so it is exhaustively
testable and produces a *recorded reason* for every exclusion. Reasons matter
downstream: "the tool never looked at that file" and "the tool read it and
found nothing" are different answers to a user's question.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum, unique
from typing import Final

from issuepilot.repository.domain.values import CommitSha, RelativeRepoPath, RepositoryRef


@unique
class ExclusionReason(Enum):
    BINARY = "binary"
    MEDIA_OR_ARCHIVE = "media-or-archive"
    BUILD_OUTPUT = "build-output"
    VENDORED = "vendored"
    MINIFIED = "minified"
    TOO_LARGE = "too-large"
    SECRET_LIKE = "secret-like"  # noqa: S105 - an exclusion reason, not a credential


# Extensions carrying no reviewable source text.
_MEDIA_SUFFIXES: Final = frozenset(
    {
        ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".tiff", ".svg",
        ".mp3", ".wav", ".flac", ".ogg", ".m4a",
        ".mp4", ".avi", ".mov", ".mkv", ".webm",
        ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar", ".jar", ".war",
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
        ".woff", ".woff2", ".ttf", ".otf", ".eot",
        ".so", ".dylib", ".dll", ".exe", ".bin", ".o", ".a", ".class", ".pyc",
    }
)  # fmt: skip

# Directory names that mark generated output anywhere in a path.
_BUILD_DIRS: Final = frozenset(
    {
        "build", "dist", "out", "target", "bin", "obj",
        "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox",
        ".next", ".nuxt", ".parcel-cache", ".gradle", ".terraform",
        "coverage", "htmlcov", ".nyc_output",
    }
)  # fmt: skip

# Directory names that mark third-party code we did not write.
_VENDOR_DIRS: Final = frozenset(
    {"node_modules", "vendor", "third_party", "thirdparty", "bower_components", ".venv", "venv"}
)

# Files whose *contents* are credentials. Excluded before any indexing so
# secrets never reach an embedding model or a report.
_SECRET_NAMES: Final = frozenset(
    {
        ".env", ".env.local", ".env.production", ".env.development", ".netrc", ".npmrc",
        ".pgpass", "credentials", "credentials.json", "service-account.json",
        ".htpasswd", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
    }
)  # fmt: skip
_SECRET_SUFFIXES: Final = frozenset({".pem", ".key", ".p12", ".pfx", ".keystore", ".jks"})
_SECRET_PREFIXES: Final = (".env.",)

_MINIFIED_MARKERS: Final = (".min.js", ".min.css", ".bundle.js", "-min.js")

_LANGUAGE_BY_SUFFIX: Final = {
    ".py": "Python", ".pyi": "Python",
    ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript",
    ".go": "Go", ".rs": "Rust", ".rb": "Ruby", ".php": "PHP",
    ".java": "Java", ".kt": "Kotlin", ".scala": "Scala", ".swift": "Swift",
    ".c": "C", ".h": "C", ".cc": "C++", ".cpp": "C++", ".hpp": "C++", ".cs": "C#",
    ".sh": "Shell", ".bash": "Shell", ".zsh": "Shell",
    ".sql": "SQL", ".md": "Markdown", ".rst": "reStructuredText",
    ".yml": "YAML", ".yaml": "YAML", ".json": "JSON", ".toml": "TOML", ".ini": "INI",
    ".html": "HTML", ".css": "CSS", ".scss": "CSS",
}  # fmt: skip


def detect_language(path: RelativeRepoPath) -> str | None:
    return _LANGUAGE_BY_SUFFIX.get(_suffix(path.value))


def _suffix(value: str) -> str:
    name = value.rsplit("/", 1)[-1]
    dot = name.rfind(".")
    return name[dot:].lower() if dot > 0 else ""


@dataclass(frozen=True, slots=True)
class FileEligibilityPolicy:
    """Decides which tracked files may be read, indexed, and cited."""

    max_file_bytes: int

    def __post_init__(self) -> None:
        if self.max_file_bytes < 1:
            raise ValueError(f"max_file_bytes must be positive, got {self.max_file_bytes}")

    def evaluate(
        self, path: RelativeRepoPath, size_bytes: int, *, is_binary: bool
    ) -> ExclusionReason | None:
        """Return the reason this file is excluded, or None when eligible.

        Secret-like files are checked first: an oversized ``.env`` should be
        reported as a secret, not as a size problem.
        """
        name = path.value.rsplit("/", 1)[-1].lower()
        parts = [p.lower() for p in path.value.split("/")[:-1]]

        if (
            name in _SECRET_NAMES
            or _suffix(path.value) in _SECRET_SUFFIXES
            or name.startswith(_SECRET_PREFIXES)
        ):
            return ExclusionReason.SECRET_LIKE
        if any(part in _VENDOR_DIRS for part in parts):
            return ExclusionReason.VENDORED
        if any(part in _BUILD_DIRS for part in parts):
            return ExclusionReason.BUILD_OUTPUT
        if any(marker in name for marker in _MINIFIED_MARKERS):
            return ExclusionReason.MINIFIED
        if _suffix(path.value) in _MEDIA_SUFFIXES:
            return ExclusionReason.MEDIA_OR_ARCHIVE
        if is_binary:
            return ExclusionReason.BINARY
        if size_bytes > self.max_file_bytes:
            return ExclusionReason.TOO_LARGE
        return None


@dataclass(frozen=True, slots=True)
class FileEntry:
    path: RelativeRepoPath
    size_bytes: int
    language: str | None = None

    def __post_init__(self) -> None:
        if self.size_bytes < 0:
            raise ValueError(f"file size cannot be negative, got {self.size_bytes}")


@dataclass(frozen=True, slots=True)
class ExcludedFile:
    path: RelativeRepoPath
    reason: ExclusionReason


@dataclass(frozen=True, slots=True)
class RepositoryManifest:
    """The analyzable surface of one snapshot, with exclusions accounted for."""

    commit_sha: CommitSha
    requested_ref: RepositoryRef
    included: tuple[FileEntry, ...]
    excluded: tuple[ExcludedFile, ...]

    def __post_init__(self) -> None:
        overlap = {e.path.value for e in self.included} & {e.path.value for e in self.excluded}
        if overlap:
            raise ValueError(f"files cannot be both included and excluded: {sorted(overlap)}")

    @property
    def included_count(self) -> int:
        return len(self.included)

    @property
    def excluded_count(self) -> int:
        return len(self.excluded)

    @property
    def total_bytes(self) -> int:
        return sum(entry.size_bytes for entry in self.included)

    def language_distribution(self) -> dict[str, int]:
        """File counts per detected language, most common first."""
        counter = Counter(e.language for e in self.included if e.language is not None)
        return dict(counter.most_common())

    def exclusion_counts(self) -> dict[str, int]:
        counter = Counter(e.reason.value for e in self.excluded)
        return dict(sorted(counter.items()))
