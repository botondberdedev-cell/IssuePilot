"""Contract suite for ReasoningModelPort (Ollama adapter joins in v0.1,
marked ``ollama``)."""

from __future__ import annotations

import pytest

from issuepilot.investigation.application.ports import ModelRequest, ReasoningModelPort
from tests.support.fakes.reasoning import FakeReasoningModel


@pytest.fixture(params=["fake"])
def model(request: pytest.FixtureRequest) -> ReasoningModelPort:
    return FakeReasoningModel(["first answer", "second answer"])


def test_complete_returns_nonempty_text(model: ReasoningModelPort) -> None:
    answer = model.complete(ModelRequest(prompt="What is affected?"))
    assert isinstance(answer, str)
    assert answer.strip()


def test_fake_returns_scripted_responses_in_order() -> None:
    fake = FakeReasoningModel(["one", "two"])
    assert fake.complete(ModelRequest(prompt="p1")) == "one"
    assert fake.complete(ModelRequest(prompt="p2")) == "two"
    assert [r.prompt for r in fake.requests] == ["p1", "p2"]


def test_fake_raises_when_script_exhausted() -> None:
    fake = FakeReasoningModel(["only"])
    fake.complete(ModelRequest(prompt="p"))
    with pytest.raises(RuntimeError, match="exhausted"):
        fake.complete(ModelRequest(prompt="p"))
