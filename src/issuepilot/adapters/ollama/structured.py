"""Schema-constrained generation with bounded repair.

Ollama constrains decoding to the supplied JSON schema, which in practice
makes malformed output rare — but "rare" is not "never", and a run that dies
on one bad token wastes the whole investigation. One repair attempt is
allowed: the failure is shown back to the model and the call retried.

The retry budget is deliberately small. A model that cannot produce valid
JSON twice in a row will not produce it on the fifth try either, and each
attempt costs real seconds.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Final

from issuepilot.adapters.ollama.client import ChatResponse, OllamaClient
from issuepilot.shared_kernel.errors import ModelUnavailableError

MAX_REPAIR_ATTEMPTS: Final = 1


@dataclass(frozen=True, slots=True)
class StructuredResult:
    data: dict[str, Any]
    prompt_tokens: int
    completion_tokens: int
    duration_ns: int
    repairs: int

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class StructuredGenerator:
    def __init__(self, client: OllamaClient, model: str, *, keep_alive: str | None = None) -> None:
        self._client = client
        self._model = model
        self._keep_alive = keep_alive

    def generate(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any],
    ) -> StructuredResult:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        prompt_tokens = completion_tokens = duration = 0

        for attempt in range(MAX_REPAIR_ATTEMPTS + 1):
            response = self._client.chat(
                self._model, messages, json_schema=schema, keep_alive=self._keep_alive
            )
            prompt_tokens += response.prompt_tokens
            completion_tokens += response.completion_tokens
            duration += response.total_duration_ns

            parsed, problem = _parse(response)
            if parsed is not None:
                return StructuredResult(
                    data=parsed,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    duration_ns=duration,
                    repairs=attempt,
                )
            if attempt == MAX_REPAIR_ATTEMPTS:
                break
            messages = [
                *messages,
                {"role": "assistant", "content": response.content},
                {
                    "role": "user",
                    "content": (
                        f"That was not valid JSON for the schema ({problem}). "
                        "Reply with the corrected JSON object and nothing else."
                    ),
                },
            ]

        raise ModelUnavailableError(
            f"model {self._model!r} did not return schema-valid JSON after "
            f"{MAX_REPAIR_ATTEMPTS + 1} attempts",
            remediation="try a larger chat model, or reduce the prompt size",
        )


def _parse(response: ChatResponse) -> tuple[dict[str, Any] | None, str]:
    content = response.content.strip()
    if not content:
        return None, "empty response"
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        return None, f"parse error: {exc.msg}"
    if not isinstance(parsed, dict):
        return None, f"expected a JSON object, got {type(parsed).__name__}"
    return parsed, ""
