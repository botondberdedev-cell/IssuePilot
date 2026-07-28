"""The composed application boots against the real local environment."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from issuepilot.adapters.sqlite.connection import connect
from issuepilot.adapters.sqlite.migrator import migrate
from issuepilot.bootstrap.config import AppConfig, load_config
from issuepilot.bootstrap.entry import build_services, open_database, run_cli

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def isolated_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def connection(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    conn = connect(tmp_path / "workspace" / "issuepilot.db")
    migrate(conn)
    try:
        yield conn
    finally:
        conn.close()


def test_build_services_composes_from_real_config(
    tmp_path: Path, connection: sqlite3.Connection
) -> None:
    config = AppConfig(workspace_dir=tmp_path / "workspace")
    services = build_services(config, connection)
    assert services.environment_checks
    assert "models" in services.config_dump
    assert services.repository is not None


def test_open_database_applies_migrations(tmp_path: Path) -> None:
    config = AppConfig(workspace_dir=tmp_path / "fresh")
    conn = open_database(config)
    try:
        tables = {
            row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert "rep_snapshots" in tables
        assert "outbox_events" in tables
    finally:
        conn.close()


def test_config_validate_through_real_composition(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run_cli(["config", "validate"]) == 0
    assert "valid" in capsys.readouterr().out


def test_invalid_config_file_exits_with_usage_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "issuepilot.toml").write_text("[investigation]\nmax_steps = -3\n", encoding="utf-8")
    assert run_cli(["config", "validate"]) == 2
    assert "invalid configuration" in capsys.readouterr().err


def test_default_config_loads_in_an_isolated_directory() -> None:
    assert load_config().models.chat
