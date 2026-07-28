from __future__ import annotations

from pathlib import Path

import pytest

from issuepilot.bootstrap.config import config_hash, load_config, redacted_dump
from issuepilot.shared_kernel.errors import UsageError


@pytest.fixture(autouse=True)
def isolate_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep tests independent of the developer's real config files and env."""
    monkeypatch.chdir(tmp_path)
    for var in list(__import__("os").environ):
        if var.startswith("ISSUEPILOT_"):
            monkeypatch.delenv(var)


def test_defaults_load_without_any_file() -> None:
    config = load_config()
    assert config.models.chat == "qwen3"
    assert config.investigation.max_steps == 12
    assert config.execution.enabled is False


def test_toml_file_overrides_defaults(tmp_path: Path) -> None:
    config_file = tmp_path / "custom.toml"
    config_file.write_text(
        '[models]\nchat = "llama3.3"\n\n[investigation]\nmax_steps = 5\n',
        encoding="utf-8",
    )
    config = load_config(config_file)
    assert config.models.chat == "llama3.3"
    assert config.investigation.max_steps == 5
    assert config.models.embedding == "embeddinggemma"  # untouched default


def test_env_overrides_toml(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_file = tmp_path / "custom.toml"
    config_file.write_text('[models]\nchat = "from-toml"\n', encoding="utf-8")
    monkeypatch.setenv("ISSUEPILOT_MODELS__CHAT", "from-env")
    config = load_config(config_file)
    assert config.models.chat == "from-env"


def test_invalid_values_raise_usage_error(tmp_path: Path) -> None:
    config_file = tmp_path / "custom.toml"
    config_file.write_text("[investigation]\nmax_steps = 0\n", encoding="utf-8")
    with pytest.raises(UsageError, match="invalid configuration"):
        load_config(config_file)


def test_missing_explicit_file_raises_usage_error(tmp_path: Path) -> None:
    with pytest.raises(UsageError, match="not found"):
        load_config(tmp_path / "nope.toml")


def test_dump_and_hash_are_stable() -> None:
    a, b = load_config(), load_config()
    assert redacted_dump(a) == redacted_dump(b)
    assert config_hash(a) == config_hash(b)


def test_config_hash_changes_with_content(tmp_path: Path) -> None:
    config_file = tmp_path / "custom.toml"
    config_file.write_text('[models]\nchat = "different"\n', encoding="utf-8")
    assert config_hash(load_config(config_file)) != config_hash(load_config())
