"""The composed application boots against the real local environment."""

from __future__ import annotations

from pathlib import Path

import pytest

from issuepilot.bootstrap.entry import build_services, run_cli

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def isolated_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)


def test_build_services_composes_from_real_config() -> None:
    services = build_services()
    assert services.environment_checks
    assert "models" in services.config_dump


def test_config_validate_through_real_composition(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run_cli(["config", "validate"]) == 0
    assert "valid" in capsys.readouterr().out


def test_invalid_config_file_exits_with_usage_code(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "issuepilot.toml").write_text("[investigation]\nmax_steps = -3\n", encoding="utf-8")
    assert run_cli(["config", "validate"]) == 2
    assert "invalid configuration" in capsys.readouterr().err
