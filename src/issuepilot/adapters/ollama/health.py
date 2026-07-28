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
        """Match with and without a tag suffix (``qwen3`` matches ``qwen3:latest``)."""
        return any(m == name or m.split(":", 1)[0] == name for m in self.models)


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
