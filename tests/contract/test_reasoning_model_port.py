"""Contract suite for ReasoningModelPort.

The ``ollama``-marked parameter exercises the real structured generator: this
is the check that a local model can hold a JSON schema, which the whole ReAct
design depends on.
"""

from __future__ import annotations

import pytest

from issuepilot.adapters.ollama.client import OllamaClient
from issuepilot.adapters.ollama.structured import StructuredGenerator
from issuepilot.bootstrap.wiring.investigation import OllamaReasoningModel
from issuepilot.investigation.application.ports import ReasoningModelPort, StructuredRequest
from tests.support.fakes.investigation import ScriptedReasoningModel

OLLAMA_URL = "http://127.0.0.1:11434"
CHAT_MODEL = "qwen3:8b"

SCHEMA = {
    "type": "object",
    "properties": {
        "reason": {"type": "string"},
        "tool": {"type": "string", "enum": ["search_text", "finish"]},
    },
    "required": ["reason", "tool"],
}


@pytest.fixture(
    params=[
        pytest.param("fake", id="fake"),
        pytest.param("ollama", id="real", marks=pytest.mark.ollama),
    ]
)
def model(request: pytest.FixtureRequest) -> ReasoningModelPort:
    if request.param == "fake":
        return ScriptedReasoningModel([{"reason": "scripted", "tool": "search_text"}] * 4)
    return OllamaReasoningModel(StructuredGenerator(OllamaClient(OLLAMA_URL), CHAT_MODEL))


def request_for(step: int = 1) -> StructuredRequest:
    return StructuredRequest(
        prompt_name="react_step@v1",
        system="You investigate repositories. Respond with JSON only.",
        user=(
            "Issue: refunds stay pending after a webhook retry.\n"
            f"Step {step}. Choose one tool: search_text or finish."
        ),
        schema=SCHEMA,
    )


def test_returns_data_matching_the_schema(model: ReasoningModelPort) -> None:
    reply = model.generate(request_for())
    assert set(reply.data) >= {"reason", "tool"}
    assert reply.data["tool"] in {"search_text", "finish"}


def test_reply_values_have_the_declared_types(model: ReasoningModelPort) -> None:
    reply = model.generate(request_for())
    assert isinstance(reply.data["reason"], str)
    assert isinstance(reply.data["tool"], str)


def test_schema_holds_across_consecutive_calls(model: ReasoningModelPort) -> None:
    """A ReAct run makes many sequential calls; one valid reply is not enough."""
    for step in range(1, 4):
        reply = model.generate(request_for(step))
        assert reply.data["tool"] in {"search_text", "finish"}


def test_token_accounting_is_reported(model: ReasoningModelPort) -> None:
    reply = model.generate(request_for())
    assert reply.total_tokens == reply.prompt_tokens + reply.completion_tokens
