from __future__ import annotations

from issuepilot.feedback.application.use_cases.export_candidates import export_candidates
from issuepilot.feedback.domain.feedback import FeedbackKind, UserFeedback
from issuepilot.shared_kernel.ids import FeedbackId, RunId

RUN_A, RUN_B, RUN_C = RunId("run-a"), RunId("run-b"), RunId("run-c")
ISSUES = {"run-a": "Refunds stuck.", "run-b": "Timeouts.", "run-c": "Slow queries."}


def entry(run_id: RunId, kind: FeedbackKind, note: str = "") -> UserFeedback:
    return UserFeedback(feedback_id=FeedbackId(f"fb-{run_id}"), run_id=run_id, kind=kind, note=note)


def test_accepted_runs_are_not_exported() -> None:
    """The suite is built from what went wrong, not from what worked."""
    drafts = export_candidates([entry(RUN_A, FeedbackKind.ACCEPT)], ISSUES)
    assert drafts == []


def test_a_rejection_becomes_a_draft() -> None:
    (draft,) = export_candidates([entry(RUN_A, FeedbackKind.REJECT, "wrong file")], ISSUES)
    assert draft.run_id == RUN_A
    assert draft.issue == "Refunds stuck."
    assert draft.note == "wrong file"


def test_a_correction_is_categorized_as_a_misleading_issue() -> None:
    (draft,) = export_candidates(
        [entry(RUN_B, FeedbackKind.CORRECT, "actually the state machine")], ISSUES
    )
    assert draft.suggested_category == "misleading-issue"


def test_a_run_whose_issue_is_unknown_is_skipped() -> None:
    """Without the original issue there is nothing to build a case from."""
    assert export_candidates([entry(RunId("gone"), FeedbackKind.REJECT)], ISSUES) == []


def test_a_note_free_rejection_still_records_why() -> None:
    (draft,) = export_candidates([entry(RUN_C, FeedbackKind.REJECT)], ISSUES)
    assert "reject" in draft.note


def test_the_stub_leaves_blanks_a_human_must_fill() -> None:
    import json

    (draft,) = export_candidates([entry(RUN_A, FeedbackKind.REJECT)], ISSUES)
    payload = json.loads(draft.to_jsonl_stub())
    assert "TODO" in payload["fixture"]
    assert "TODO" in payload["expected_paths"][0]
