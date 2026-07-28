"""Stub CLI services, for driving the CLI without any real backend."""

from __future__ import annotations

from collections.abc import Sequence

from issuepilot.investigation.application.dto import FindingDTO, ReportDTO
from issuepilot.knowledge.application.dto import IndexStatsDTO, SearchHitDTO
from issuepilot.repository.application.dto import ManifestDTO, SnapshotDTO

DEFAULT_SHA = "4f2a7c" + "0" * 34


def sample_snapshot(commit_sha: str = DEFAULT_SHA) -> SnapshotDTO:
    return SnapshotDTO(
        snapshot_id="01SNAPSHOT0000000000000000",
        commit_sha=commit_sha,
        requested_ref="main",
        locator_fingerprint="fp-1",
        root_path="/snapshots/fp-1",
    )


def sample_manifest(commit_sha: str = DEFAULT_SHA) -> ManifestDTO:
    return ManifestDTO(
        commit_sha=commit_sha,
        requested_ref="main",
        included_count=3,
        excluded_count=2,
        total_bytes=2048,
        languages={"Python": 2, "Markdown": 1},
        exclusions={"secret-like": 1, "media-or-archive": 1},
        sample_paths=("src/app.py", "README.md"),
    )


def sample_hit(commit_sha: str = DEFAULT_SHA) -> SearchHitDTO:
    return SearchHitDTO(
        chunk_id="chunk-1",
        path="src/refunds/webhook.py",
        start_line=84,
        end_line=121,
        commit_sha=commit_sha,
        snippet="def handle_retry(event):\n    ...\n",
        score=0.42,
        sources=("lexical",),
        symbol="handle_retry",
    )


def sample_report(commit_sha: str = DEFAULT_SHA) -> ReportDTO:
    return ReportDTO(
        report_id="01REPORT00000000000000000",
        run_id="01RUN00000000000000000000",
        commit_sha=commit_sha,
        issue_summary="Refunds remain pending after a retry.",
        completeness="complete",
        findings=(
            FindingDTO(
                claim="The retry path returns before the transition commits.",
                confidence=0.8,
                citations=(f"src/refunds/webhook.py:84-121 @ {commit_sha[:12]}",),
                speculative=False,
            ),
        ),
        missing_information=("no production logs were available",),
    )


class StubRepositoryService:
    def __init__(self, error: Exception | None = None) -> None:
        self._error = error
        self.calls: list[tuple[str, str | None, bool]] = []

    def acquire(
        self,
        locator: str,
        *,
        ref: str | None = None,
        depth: int = 100,
        offline: bool = False,
        allow_local_path: bool = False,
    ) -> SnapshotDTO:
        self.calls.append((locator, ref, offline))
        if self._error is not None:
            raise self._error
        return sample_snapshot()

    def inspect(
        self,
        locator: str,
        *,
        ref: str | None = None,
        depth: int = 100,
        offline: bool = False,
        allow_local_path: bool = False,
    ) -> tuple[SnapshotDTO, ManifestDTO]:
        self.calls.append((locator, ref, offline))
        if self._error is not None:
            raise self._error
        return sample_snapshot(), sample_manifest()

    def recent_snapshots(self, limit: int = 20) -> Sequence[SnapshotDTO]:
        if self._error is not None:
            raise self._error
        return (sample_snapshot(),)


class StubKnowledgeService:
    def __init__(self, hits: list[SearchHitDTO] | None = None, *, indexed: bool = True) -> None:
        self._hits = hits if hits is not None else [sample_hit()]
        self._indexed = indexed
        self.built: list[str] = []

    def build_index(
        self, commit_sha: str, root_path: str, *, rebuild: bool = False
    ) -> IndexStatsDTO:
        self.built.append(commit_sha)
        return IndexStatsDTO(
            commit_sha=commit_sha, chunk_count=12, indexed_files=3, has_semantic=False
        )

    def search(self, commit_sha: str, query: str, *, limit: int = 12) -> list[SearchHitDTO]:
        return self._hits[:limit]

    def is_indexed(self, commit_sha: str) -> bool:
        return self._indexed


class StubInvestigationService:
    def __init__(self, error: Exception | None = None) -> None:
        self._error = error
        self.issues: list[str] = []

    def investigate(
        self,
        issue_text: str,
        commit_sha: str,
        root_path: str,
        *,
        max_steps: int | None = None,
        on_step: object = None,
    ) -> ReportDTO:
        self.issues.append(issue_text)
        if self._error is not None:
            raise self._error
        return sample_report(commit_sha)

    def recent_reports(self, limit: int = 20) -> Sequence[ReportDTO]:
        return (sample_report(),)

    def get_report(self, run_id: str) -> ReportDTO | None:
        return sample_report()
