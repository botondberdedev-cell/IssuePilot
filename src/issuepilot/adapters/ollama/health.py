"""Ollama daemon health and model availability probe."""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx


@dataclass(frozen=True, slots=True)
class OllamaHealth:
    reachable: bool
    models: tuple[str, ...] = field(default_factory=tuple)
    error: str | None = None

    def has_model(self, name: str) -> bool:
        """Whether Ollama would resolve ``name`` to an installed model.

        Ollama resolves a bare name to ``name:latest`` — it does *not* fall
        back to some other tag. Matching on the prefix instead would report
        ``qwen3`` as available when only ``qwen3:8b`` is installed, so doctor
        would pass and the first real request would fail with a 404.
        """
        wanted = name if ":" in name else f"{name}:latest"
        return wanted in self.models


def check_health(base_url: str, *, timeout_seconds: float = 3.0) -> OllamaHealth:
    try:
        response = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=timeout_seconds)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as exc:
        return OllamaHealth(reachable=False, error=str(exc))
    models = tuple(
        str(entry["name"]) for entry in payload.get("models", []) if isinstance(entry, dict)
    )
    return OllamaHealth(reachable=True, models=models)
