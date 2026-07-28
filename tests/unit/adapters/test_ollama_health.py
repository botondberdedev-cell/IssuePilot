from __future__ import annotations

from typing import Any

import httpx
import pytest

from issuepilot.adapters.ollama.health import OllamaHealth, check_health


def test_unreachable_daemon_reports_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(url: str, timeout: float) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "get", refuse)
    health = check_health("http://127.0.0.1:1")
    assert not health.reachable
    assert health.error is not None
    assert health.models == ()


def test_reachable_daemon_lists_models(monkeypatch: pytest.MonkeyPatch) -> None:
    payload: dict[str, Any] = {
        "models": [{"name": "qwen3:latest"}, {"name": "embeddinggemma:300m"}, "junk-entry"]
    }

    def respond(url: str, timeout: float) -> httpx.Response:
        assert url.endswith("/api/tags")
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", respond)
    health = check_health("http://127.0.0.1:11434/")
    assert health.reachable
    assert health.models == ("qwen3:latest", "embeddinggemma:300m")


def test_http_error_status_is_not_reachable(monkeypatch: pytest.MonkeyPatch) -> None:
    def respond(url: str, timeout: float) -> httpx.Response:
        return httpx.Response(500, json={}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", respond)
    assert not check_health("http://127.0.0.1:11434").reachable


def test_bare_name_resolves_to_the_latest_tag() -> None:
    health = OllamaHealth(reachable=True, models=("qwen3:latest",))
    assert health.has_model("qwen3")
    assert health.has_model("qwen3:latest")


def test_bare_name_does_not_match_a_different_tag() -> None:
    """Ollama resolves 'qwen3' to 'qwen3:latest' only. Reporting a match
    against 'qwen3:8b' would make doctor pass and the first request 404."""
    health = OllamaHealth(reachable=True, models=("qwen3:8b",))
    assert not health.has_model("qwen3")
    assert health.has_model("qwen3:8b")


def test_unknown_model_is_absent() -> None:
    health = OllamaHealth(reachable=True, models=("qwen3:8b",))
    assert not health.has_model("llama3")
