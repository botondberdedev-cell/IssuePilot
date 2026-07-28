"""The ReAct loop, driven by scripted model transcripts.

Every safety property here must hold regardless of what the model says, so
each test scripts a hostile or degenerate transcript and asserts the loop
constrains it.
"""

from __future__ import annotations

from typing import Any

import pytest

from issuepilot.investigation.application.dto import EvidenceCandidateDTO
from issuepilot.investigation.application.strategies.react import ReActStrategy
from issuepilot.investigation.domain.budget import StepBudget
from issuepilot.investigation.domain.values import IssueStatement
from issuepilot.shared_kernel.cancellation import CancellationToken
from issuepilot.shared_kernel.errors import OperationInterruptedError
from tests.support.fakes.investigation import (
    FakeCitationVerifier,
    FakeFileReader,
    FakePrompts,
    FakeSearch,
    ScriptedReasoningModel,
)

SHA = "a" * 40
ISSUE = IssueStatement("Refunds remain pending after a webhook retry.")


def candidate(path: str = "src/webhook.py", score: float = 0.9) -> EvidenceCandidateDTO:
    return EvidenceCandidateDTO(
        path=path,
        start_line=10,
        end_line=20,
        snippet="def handle_retry(event):\n    ...\n",
        score=score,
        commit_sha=SHA,
        symbol="handle_retry",
    )


def build(
    replies: list[dict[str, Any]],
    *,
    candidates: list[EvidenceCandidateDTO] | None = None,
    files: dict[str, str] | None = None,
    verify_all: bool = True,
) -> tuple[ReActStrategy, ScriptedReasoningModel, FakeSearch, FakeFileReader]:
    model = ScriptedReasoningModel(replies)
    search = FakeSearch(candidates if candidates is not None else [candidate()])
    reader = FakeFileReader(
        files or {"src/webhook.py": "".join(f"line {i}\n" for i in range(1, 40))}
    )
    verifier = FakeCitationVerifier()
    verifier.allow_all = verify_all
    strategy = ReActStrategy(
        model=model,
        prompts=FakePrompts(),
        search=search,
        reader=reader,
        verifier=verifier,
        commit_sha=SHA,
        file_count=3,
    )
    return strategy, model, search, reader


class TestControlFlow:
    def test_finish_ends_the_loop_immediately(self) -> None:
        strategy, _, _, _ = build([{"reason": "done", "tool": "finish"}])
        outcome = strategy.investigate(ISSUE, StepBudget(limit=5))
        assert outcome.steps == ()
        assert not outcome.budget_exhausted

    def test_search_then_finish_collects_evidence(self) -> None:
        strategy, _, search, _ = build(
            [
                {"reason": "look", "tool": "search_text", "query": "handle_retry"},
                {"reason": "done", "tool": "finish"},
            ]
        )
        outcome = strategy.investigate(ISSUE, StepBudget(limit=5))
        assert len(outcome.steps) == 1
        assert search.queries == ["handle_retry"]
        assert outcome.evidence

    def test_reading_a_file_becomes_evidence(self) -> None:
        strategy, _, _, reader = build(
            [
                {
                    "reason": "read",
                    "tool": "read_file",
                    "path": "src/webhook.py",
                    "start_line": 1,
                    "end_line": 5,
                },
                {"reason": "done", "tool": "finish"},
            ]
        )
        outcome = strategy.investigate(ISSUE, StepBudget(limit=5))
        assert reader.reads == [("src/webhook.py", 1, 5)]
        assert any(e.path == "src/webhook.py" for e in outcome.evidence)

    def test_hypotheses_are_recorded(self) -> None:
        strategy, _, _, _ = build(
            [
                {"reason": "note", "tool": "record_hypothesis", "hypothesis": "dedup races"},
                {"reason": "done", "tool": "finish"},
            ]
        )
        outcome = strategy.investigate(ISSUE, StepBudget(limit=5))
        assert outcome.hypotheses == ("dedup races",)

    def test_steps_are_reported_as_they_happen(self) -> None:
        seen: list[int] = []
        strategy, _, _, _ = build(
            [
                {"reason": "a", "tool": "search_text", "query": "x"},
                {"reason": "b", "tool": "search_text", "query": "y"},
                {"reason": "done", "tool": "finish"},
            ]
        )
        strategy.investigate(ISSUE, StepBudget(limit=5), on_step=lambda s: seen.append(s.index))
        assert seen == [1, 2]


class TestBudget:
    def test_loop_stops_at_the_budget_even_if_the_model_never_finishes(self) -> None:
        replies = [{"reason": "again", "tool": "search_text", "query": "x"}] * 20
        strategy, _, _, _ = build(replies)
        outcome = strategy.investigate(ISSUE, StepBudget(limit=3))
        assert len(outcome.steps) == 3
        assert outcome.budget_exhausted

    def test_budget_of_one_allows_exactly_one_step(self) -> None:
        replies = [{"reason": "go", "tool": "search_text", "query": "x"}] * 5
        strategy, _, _, _ = build(replies)
        outcome = strategy.investigate(ISSUE, StepBudget(limit=1))
        assert len(outcome.steps) == 1


class TestHostileModelOutput:
    def test_unknown_tool_ends_the_run_rather_than_crashing(self) -> None:
        strategy, _, _, _ = build([{"reason": "sneaky", "tool": "run_shell_command"}])
        outcome = strategy.investigate(ISSUE, StepBudget(limit=5))
        assert outcome.steps == ()

    def test_search_without_a_query_is_reported_not_executed(self) -> None:
        strategy, _, search, _ = build(
            [
                {"reason": "oops", "tool": "search_text"},
                {"reason": "done", "tool": "finish"},
            ]
        )
        outcome = strategy.investigate(ISSUE, StepBudget(limit=5))
        assert search.queries == []
        assert "No query supplied" in outcome.steps[0].observation

    def test_read_without_a_path_is_reported_not_executed(self) -> None:
        strategy, _, _, reader = build(
            [
                {"reason": "oops", "tool": "read_file"},
                {"reason": "done", "tool": "finish"},
            ]
        )
        outcome = strategy.investigate(ISSUE, StepBudget(limit=5))
        assert reader.reads == []
        assert "No path supplied" in outcome.steps[0].observation

    def test_unverifiable_path_is_refused_before_reading(self) -> None:
        strategy, _, _, reader = build(
            [
                {"reason": "escape", "tool": "read_file", "path": "../../etc/passwd"},
                {"reason": "done", "tool": "finish"},
            ],
            verify_all=False,
        )
        outcome = strategy.investigate(ISSUE, StepBudget(limit=5))
        assert reader.reads == []
        assert "not readable in this snapshot" in outcome.steps[0].observation

    def test_read_range_is_capped(self) -> None:
        strategy, _, _, reader = build(
            [
                {
                    "reason": "huge",
                    "tool": "read_file",
                    "path": "src/webhook.py",
                    "start_line": 1,
                    "end_line": 10_000,
                },
                {"reason": "done", "tool": "finish"},
            ]
        )
        strategy.investigate(ISSUE, StepBudget(limit=5))
        (_, start, end) = reader.reads[0]
        assert end - start + 1 <= 200

    def test_evidence_from_another_snapshot_is_discarded(self) -> None:
        foreign = EvidenceCandidateDTO(
            path="other.py",
            start_line=1,
            end_line=2,
            snippet="x",
            score=1.0,
            commit_sha="b" * 40,
        )
        strategy, _, _, _ = build(
            [
                {"reason": "look", "tool": "search_text", "query": "x"},
                {"reason": "done", "tool": "finish"},
            ],
            candidates=[foreign],
        )
        outcome = strategy.investigate(ISSUE, StepBudget(limit=5))
        assert outcome.evidence == ()


class TestCancellation:
    def test_cancellation_stops_before_the_first_model_call(self) -> None:
        strategy, model, _, _ = build([{"reason": "x", "tool": "finish"}])
        token = CancellationToken()
        token.cancel()
        with pytest.raises(OperationInterruptedError):
            strategy.investigate(ISSUE, StepBudget(limit=5), cancellation=token)
        assert model.requests == []


class TestTimeBudget:
    def test_running_out_of_time_ends_the_run_and_marks_it_incomplete(self) -> None:
        """A timeout keeps the evidence gathered so far rather than discarding it."""
        replies = [{"reason": "again", "tool": "search_text", "query": "x"}] * 10
        strategy, _, _, _ = build(replies)
        calls = {"n": 0}

        def out_of_time() -> bool:
            calls["n"] += 1
            return calls["n"] > 2  # allow two iterations, then expire

        outcome = strategy.investigate(ISSUE, StepBudget(limit=9), out_of_time=out_of_time)
        assert outcome.timed_out
        assert outcome.budget_exhausted
        assert len(outcome.steps) == 2
        assert outcome.evidence

    def test_a_generous_budget_does_not_interfere(self) -> None:
        strategy, _, _, _ = build(
            [
                {"reason": "look", "tool": "search_text", "query": "x"},
                {"reason": "done", "tool": "finish"},
            ]
        )
        outcome = strategy.investigate(ISSUE, StepBudget(limit=5), out_of_time=lambda: False)
        assert not outcome.timed_out
