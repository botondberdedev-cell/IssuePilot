"""HTTP client for a local Ollama daemon.

Failures map onto ``ModelUnavailableError`` (exit code 4) with remediation,
because "the model isn't there" is an environment problem the user can fix,
not an internal fault.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

import httpx

from issuepilot.shared_kernel.errors import ModelUnavailableError

DEFAULT_TIMEOUT: Final = 180.0
_EMBED_TIMEOUT: Final = 300.0


@dataclass(frozen=True, slots=True)
class ChatResponse:
    content: str
    prompt_tokens: int
    completion_tokens: int
    total_duration_ns: int

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class OllamaClient:
    def __init__(self, base_url: str, *, timeout_seconds: float = DEFAULT_TIMEOUT) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    def embed(self, model: str, inputs: list[str]) -> list[tuple[float, ...]]:
        """Embed a batch. Ollama returns unit-length vectors, so a downstream
        dot product is a cosine similarity."""
        payload = self._post(
            "/api/embed", {"model": model, "input": inputs}, timeout=_EMBED_TIMEOUT
        )
        embeddings = payload.get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != len(inputs):
            raise ModelUnavailableError(
                f"embedding model {model!r} returned {len(embeddings or [])} vectors "
                f"for {len(inputs)} inputs",
                remediation=f"verify the model with `ollama show {model}`",
            )
        return [tuple(float(x) for x in vector) for vector in embeddings]

    def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        json_schema: dict[str, Any] | None = None,
        temperature: float = 0.0,
        keep_alive: str | None = None,
    ) -> ChatResponse:
        """One non-streaming chat turn, optionally schema-constrained.

        Temperature defaults to 0 and thinking is disabled: an investigation
        should be as reproducible as the runtime allows, and reasoning models
        otherwise spend most of their latency on tokens we discard.
        """
        request: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "think": False,
            "options": {"temperature": temperature},
        }
        if json_schema is not None:
            request["format"] = json_schema
        if keep_alive is not None:
            request["keep_alive"] = keep_alive

        payload = self._post("/api/chat", request, timeout=self._timeout)
        message = payload.get("message") or {}
        return ChatResponse(
            content=str(message.get("content", "")),
            prompt_tokens=int(payload.get("prompt_eval_count", 0)),
            completion_tokens=int(payload.get("eval_count", 0)),
            total_duration_ns=int(payload.get("total_duration", 0)),
        )

    def _post(self, path: str, body: dict[str, Any], *, timeout: float) -> dict[str, Any]:
        try:
            response = httpx.post(f"{self._base_url}{path}", json=body, timeout=timeout)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise ModelUnavailableError(
                f"ollama rejected the request: {exc.response.status_code} "
                f"{exc.response.text[:200]}",
                remediation="check the model name in issuepilot.toml against `ollama list`",
            ) from exc
        except httpx.HTTPError as exc:
            raise ModelUnavailableError(
                f"cannot reach ollama at {self._base_url}: {exc}",
                remediation="start it with `ollama serve`",
            ) from exc
        if not isinstance(payload, dict):
            raise ModelUnavailableError("ollama returned an unexpected response shape")
        return payload
