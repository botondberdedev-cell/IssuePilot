from __future__ import annotations

import pytest

from issuepilot.repository.domain.manifest import (
    ExcludedFile,
    ExclusionReason,
    FileEligibilityPolicy,
    FileEntry,
    RepositoryManifest,
    detect_language,
)
from issuepilot.repository.domain.values import CommitSha, RelativeRepoPath, RepositoryRef

SHA = CommitSha("a" * 40)
POLICY = FileEligibilityPolicy(max_file_bytes=1024)


def path(value: str) -> RelativeRepoPath:
    return RelativeRepoPath(value)


class TestEligibilityPolicy:
    @pytest.mark.parametrize(
        "eligible",
        ["src/app.py", "README.md", "docs/guide/setup.rst", "pyproject.toml"],
    )
    def test_ordinary_source_is_eligible(self, eligible: str) -> None:
        assert POLICY.evaluate(path(eligible), 100, is_binary=False) is None

    @pytest.mark.parametrize(
        ("excluded", "reason"),
        [
            (".env", ExclusionReason.SECRET_LIKE),
            (".env.production", ExclusionReason.SECRET_LIKE),
            ("config/id_rsa", ExclusionReason.SECRET_LIKE),
            ("certs/server.pem", ExclusionReason.SECRET_LIKE),
            ("deploy/service-account.json", ExclusionReason.SECRET_LIKE),
            ("node_modules/left-pad/index.js", ExclusionReason.VENDORED),
            ("vendor/github.com/pkg/errors.go", ExclusionReason.VENDORED),
            ("build/output.js", ExclusionReason.BUILD_OUTPUT),
            ("src/__pycache__/app.cpython-313.pyc", ExclusionReason.BUILD_OUTPUT),
            ("static/app.min.js", ExclusionReason.MINIFIED),
            ("assets/logo.png", ExclusionReason.MEDIA_OR_ARCHIVE),
            ("dist.tar.gz", ExclusionReason.MEDIA_OR_ARCHIVE),
        ],
    )
    def test_exclusions_carry_their_reason(self, excluded: str, reason: ExclusionReason) -> None:
        assert POLICY.evaluate(path(excluded), 100, is_binary=False) is reason

    def test_binary_content_is_excluded(self) -> None:
        assert POLICY.evaluate(path("data/blob"), 100, is_binary=True) is ExclusionReason.BINARY

    def test_oversized_file_is_excluded_at_the_boundary(self) -> None:
        assert POLICY.evaluate(path("src/big.py"), 1024, is_binary=False) is None
        assert (
            POLICY.evaluate(path("src/big.py"), 1025, is_binary=False) is ExclusionReason.TOO_LARGE
        )

    def test_secret_detection_precedes_size_and_binary(self) -> None:
        """An oversized binary .env is reported as a secret, not as size."""
        assert (
            POLICY.evaluate(path(".env"), 10_000_000, is_binary=True) is ExclusionReason.SECRET_LIKE
        )

    def test_vendored_precedes_media_so_the_cause_is_the_directory(self) -> None:
        assert (
            POLICY.evaluate(path("node_modules/pkg/logo.png"), 10, is_binary=False)
            is ExclusionReason.VENDORED
        )

    def test_policy_rejects_nonpositive_size_limit(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            FileEligibilityPolicy(max_file_bytes=0)


class TestLanguageDetection:
    @pytest.mark.parametrize(
        ("file", "language"),
        [
            ("src/app.py", "Python"),
            ("web/index.tsx", "TypeScript"),
            ("main.go", "Go"),
            ("README.md", "Markdown"),
            ("Makefile", None),
            ("archive.unknownext", None),
        ],
    )
    def test_detects_language_by_suffix(self, file: str, language: str | None) -> None:
        assert detect_language(path(file)) == language

    def test_dotfile_without_suffix_has_no_language(self) -> None:
        assert detect_language(path(".gitignore")) is None


class TestRepositoryManifest:
    def _manifest(self) -> RepositoryManifest:
        return RepositoryManifest(
            commit_sha=SHA,
            requested_ref=RepositoryRef("main"),
            included=(
                FileEntry(path("src/app.py"), 400, "Python"),
                FileEntry(path("src/util.py"), 100, "Python"),
                FileEntry(path("README.md"), 50, "Markdown"),
            ),
            excluded=(
                ExcludedFile(path(".env"), ExclusionReason.SECRET_LIKE),
                ExcludedFile(path("assets/logo.png"), ExclusionReason.MEDIA_OR_ARCHIVE),
                ExcludedFile(path("build/out.js"), ExclusionReason.BUILD_OUTPUT),
            ),
        )

    def test_counts_and_total_bytes(self) -> None:
        manifest = self._manifest()
        assert manifest.included_count == 3
        assert manifest.excluded_count == 3
        assert manifest.total_bytes == 550

    def test_language_distribution_is_ordered_by_frequency(self) -> None:
        assert self._manifest().language_distribution() == {"Python": 2, "Markdown": 1}

    def test_exclusion_counts_are_grouped_by_reason(self) -> None:
        assert self._manifest().exclusion_counts() == {
            "build-output": 1,
            "media-or-archive": 1,
            "secret-like": 1,
        }

    def test_a_file_cannot_be_both_included_and_excluded(self) -> None:
        with pytest.raises(ValueError, match="both included and excluded"):
            RepositoryManifest(
                commit_sha=SHA,
                requested_ref=RepositoryRef("main"),
                included=(FileEntry(path("src/app.py"), 10),),
                excluded=(ExcludedFile(path("src/app.py"), ExclusionReason.BINARY),),
            )

    def test_negative_file_size_rejected(self) -> None:
        with pytest.raises(ValueError, match="negative"):
            FileEntry(path("src/app.py"), -1)

    def test_empty_manifest_is_valid(self) -> None:
        manifest = RepositoryManifest(
            commit_sha=SHA, requested_ref=RepositoryRef("main"), included=(), excluded=()
        )
        assert manifest.total_bytes == 0
        assert manifest.language_distribution() == {}
