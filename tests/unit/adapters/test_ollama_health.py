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


def test_has_model_matches_with_and_without_tag() -> None:
    health = OllamaHealth(reachable=True, models=("qwen3:latest", "embeddinggemma:300m"))
    assert health.has_model("qwen3")
    assert health.has_model("qwen3:latest")
    assert health.has_model("embeddinggemma")
    assert not health.has_model("llama3")
