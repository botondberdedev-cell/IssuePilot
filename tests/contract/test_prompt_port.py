"""Contract suite for PromptPort: the fake and the packaged registry."""

from __future__ import annotations

import pytest

from issuepilot.bootstrap.wiring.investigation import RegistryPromptAdapter
from issuepilot.investigation.application.ports import PromptPort
from issuepilot.investigation.infrastructure.prompt_registry import PromptRegistry
from tests.support.fakes.investigation import FakePrompts

STEP_CONTEXT = {
    "issue": "Refunds stay pending.",
    "short_sha": "4f2a7c000000",
    "file_count": 3,
    "languages": "Python",
    "steps": [],
    "remaining_steps": 5,
    "read_a_file": False,
}


@pytest.fixture(params=["fake", "registry"])
def prompts(request: pytest.FixtureRequest) -> PromptPort:
    if request.param == "fake":
        return FakePrompts()
    return RegistryPromptAdapter(PromptRegistry())


def test_rendering_returns_named_text_and_schema(prompts: PromptPort) -> None:
    rendered = prompts.render("react_step@v1", **STEP_CONTEXT)
    assert rendered.name == "react_step@v1"
    assert rendered.text.strip()
    assert rendered.schema


def test_rendering_is_deterministic(prompts: PromptPort) -> None:
    first = prompts.render("react_step@v1", **STEP_CONTEXT)
    second = prompts.render("react_step@v1", **STEP_CONTEXT)
    assert first.text == second.text


def test_context_reaches_the_output(prompts: PromptPort) -> None:
    rendered = prompts.render("react_step@v1", **STEP_CONTEXT)
    assert "Refunds stay pending." in rendered.text


def test_a_version_and_hash_are_reported(prompts: PromptPort) -> None:
    rendered = prompts.render("react_step@v1", **STEP_CONTEXT)
    assert rendered.version
    assert rendered.template_hash
