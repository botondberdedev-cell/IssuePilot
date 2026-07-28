"""Turn corrections into draft evaluation cases.

A rejection or correction is the most valuable signal the tool receives: it
marks a run that looked plausible and was wrong. Exporting those as draft
cases is what makes the evaluation dataset grow from real failures rather
than from imagination.

Drafts are deliberately incomplete — a human fills in expected paths, because
only a human knows what the right answer was.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from issuepilot.feedback.application.dto import DraftCase
from issuepilot.feedback.domain.feedback import FeedbackKind, UserFeedback


def export_candidates(
    feedback: Sequence[UserFeedback], issues_by_run: Mapping[str, str]
) -> list[DraftCase]:
    """Only rejections and corrections become candidates.

    An accepted run tells us the tool worked, which is not a case worth
    adding — the suite is built from what went wrong.
    """
    drafts: list[DraftCase] = []
    for entry in feedback:
        if entry.kind is FeedbackKind.ACCEPT:
            continue
        issue = issues_by_run.get(entry.run_id)
        if issue is None:
            continue
        drafts.append(
            DraftCase(
                run_id=entry.run_id,
                issue=issue,
                note=entry.note or f"marked {entry.kind.value}",
                suggested_category=(
                    "misleading-issue" if entry.kind is FeedbackKind.CORRECT else "bug-location"
                ),
            )
        )
    return drafts
