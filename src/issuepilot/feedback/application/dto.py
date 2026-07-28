"""Immutable DTOs crossing the feedback context's boundary."""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DraftCase:
    """A draft evaluation case built from a rejected or corrected run.

    Deliberately incomplete: only a human knows what the right answer was, so
    the blanks are left explicit rather than guessed.
    """

    run_id: str
    issue: str
    note: str
    suggested_category: str

    def to_jsonl_stub(self) -> str:
        return json.dumps(
            {
                "case_id": f"from-run-{self.run_id[:8].lower()}",
                "issue": self.issue,
                "category": self.suggested_category,
                "fixture": "TODO: name the fixture repository",
                "expected_paths": ["TODO: the file the answer should have cited"],
                "_note": self.note,
            },
            sort_keys=True,
        )
