"""``issuepilot index`` and ``issuepilot search`` end to end."""

from __future__ import annotations

import json

import pytest

from issuepilot.adapters.cli.app import run
from issuepilot.adapters.cli.services import CheckResult, CliServices
from issuepilot.shared_kernel.cancellation import CancellationToken
from issuepilot.shared_kernel.errors import ModelUnavailableError
from tests.support.fakes.services import (
    DEFAULT_SHA,
    StubEvaluationService,
    StubInvestigationService,
    StubKnowledgeService,
    StubRepositoryService,
)

pytestmark = pytest.mark.e2e

REPO = "https://example.com/a/b.git"


def services(
    knowledge: StubKnowledgeService | None = None,
    repository: StubRepositoryService | None = None,
) -> CliServices:
    return CliServices(
        version="0.0.0-test",
        cancellation=CancellationToken(),
        environment_checks=[lambda: CheckResult("git", True, "ok")],
        config_dump={},
        repository=repository or StubRepositoryService(),
        knowledge=knowledge or StubKnowledgeService(),
        investigation=StubInvestigationService(),
        evaluation=StubEvaluationService(),
    )


class TestIndex:
    def test_reports_what_was_indexed(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert run(services(), ["index", REPO]) == 0
        out = capsys.readouterr().out
        assert DEFAULT_SHA[:12] in out
        assert "chunks" in out

    def test_json_output_is_versioned(self, capsys: pytest.CaptureFixture[str]) -> None:
        run(services(), ["index", REPO, "--format", "json"])
        document = json.loads(capsys.readouterr().out)
        assert document["format_version"] == 1
        assert document["chunk_count"] == 12

    def test_rebuild_flag_is_accepted(self) -> None:
        knowledge = StubKnowledgeService()
        assert run(services(knowledge), ["index", REPO, "--rebuild"]) == 0
        assert knowledge.built == [DEFAULT_SHA]

    def test_progress_goes_to_stderr(self, capsys: pytest.CaptureFixture[str]) -> None:
        run(services(), ["index", REPO])
        captured = capsys.readouterr()
        assert "indexing" in captured.err
        assert "indexing" not in captured.out

    def test_model_unavailable_exits_four(self, capsys: pytest.CaptureFixture[str]) -> None:
        repository = StubRepositoryService(
            error=ModelUnavailableError("ollama is down", remediation="start ollama")
        )
        assert run(services(repository=repository), ["index", REPO]) == 4


class TestSearch:
    def test_prints_hits_with_location_and_source(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert run(services(), ["search", REPO, "handle_retry"]) == 0
        out = capsys.readouterr().out
        assert "src/refunds/webhook.py:84-121" in out
        assert "[lexical]" in out

    def test_json_carries_citable_coordinates(self, capsys: pytest.CaptureFixture[str]) -> None:
        run(services(), ["search", REPO, "handle_retry", "--format", "json"])
        result = json.loads(capsys.readouterr().out)["results"][0]
        assert result["path"] == "src/refunds/webhook.py"
        assert result["start_line"] == 84
        assert result["commit_sha"] == DEFAULT_SHA

    def test_markdown_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        run(services(), ["search", REPO, "handle_retry", "--format", "markdown"])
        out = capsys.readouterr().out
        assert out.startswith("# Search results")
        assert "```" in out

    def test_no_matches_is_reported_plainly(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert run(services(StubKnowledgeService(hits=[])), ["search", REPO, "nothing"]) == 0
        assert "no matches" in capsys.readouterr().out

    def test_an_unindexed_repository_is_indexed_first(self) -> None:
        knowledge = StubKnowledgeService(indexed=False)
        run(services(knowledge), ["search", REPO, "handle_retry"])
        assert knowledge.built == [DEFAULT_SHA]

    def test_an_indexed_repository_is_not_rebuilt(self) -> None:
        knowledge = StubKnowledgeService(indexed=True)
        run(services(knowledge), ["search", REPO, "handle_retry"])
        assert knowledge.built == []

    def test_limit_is_passed_through(self, capsys: pytest.CaptureFixture[str]) -> None:
        run(services(), ["search", REPO, "handle_retry", "--limit", "1", "--format", "json"])
        assert len(json.loads(capsys.readouterr().out)["results"]) == 1
