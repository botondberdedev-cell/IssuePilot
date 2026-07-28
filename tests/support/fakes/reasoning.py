from __future__ import annotations

from issuepilot.investigation.application.ports import ModelRequest


class FakeReasoningModel:
    """Deterministic scripted model: returns responses in order, records prompts."""

    def __init__(self, responses: list[str] | None = None) -> None:
        self._responses = list(responses or ["Scripted finding about the issue."])
        self.requests: list[ModelRequest] = []

    def complete(self, request: ModelRequest) -> str:
        self.requests.append(request)
        if not self._responses:
            raise RuntimeError("FakeReasoningModel script exhausted")
        return self._responses.pop(0)
