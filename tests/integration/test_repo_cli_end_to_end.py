"""The composed application against a real repository and a real database.

This is the first full vertical slice: CLI argument through bootstrap wiring,
git acquisition, manifest construction, SQLite persistence, and rendering.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from issuepilot.adapters.cli.app import run
from issuepilot.adapters.cli.services import CliServices
from issuepilot.adapters.sqlite.connection import connect
from issuepilot.adapters.sqlite.migrator import migrate
from issuepilot.bootstrap.config import AppConfig
from issuepilot.bootstrap.entry import build_services
from tests.support.fixture_repos import FixtureRepo, build_messy_repo, build_simple_repo

pytestmark = pytest.mark.integration


@pytest.fixture
def wired(tmp_path: Path) -> Iterator[CliServices]:
    config = AppConfig(workspace_dir=tmp_path / "workspace")
    connection = connect(tmp_path / "workspace" / "issuepilot.db")
    migrate(connection)
    try:
        yield build_services(config, connection)
    finally:
        connection.close()


@pytest.fixture
def source(tmp_path: Path) -> FixtureRepo:
    return build_simple_repo(tmp_path / "source")


def test_fetch_pins_the_real_commit(
    wired: CliServices, source: FixtureRepo, capsys: pytest.CaptureFixture[str]
) -> None:
    code = run(
        wired,
        ["repo", "fetch", source.locator, "--allow-local-path", "--format", "json"],
    )
    assert code == 0
    document = json.loads(capsys.readouterr().out)
    assert document["commit_sha"] == source.head_sha


def test_inspect_maps_a_messy_repository(
    wired: CliServices, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    messy = build_messy_repo(tmp_path / "messy")
    code = run(
        wired,
        ["repo", "inspect", messy.locator, "--allow-local-path", "--format", "json"],
    )
    assert code == 0
    manifest = json.loads(capsys.readouterr().out)["manifest"]

    assert manifest["languages"]["Python"] == 1
    # Every excluded file is accounted for by a recorded reason.
    assert manifest["exclusions"]["secret-like"] == 2  # .env and the .pem key
    assert manifest["exclusions"]["vendored"] == 1
    assert manifest["exclusions"]["build-output"] == 1
    assert manifest["exclusions"]["minified"] == 1
    assert sum(manifest["exclusions"].values()) == manifest["excluded_count"]


def test_status_lists_the_snapshot_after_fetch(
    wired: CliServices, source: FixtureRepo, capsys: pytest.CaptureFixture[str]
) -> None:
    run(wired, ["repo", "fetch", source.locator, "--allow-local-path", "--quiet"])
    capsys.readouterr()

    assert run(wired, ["repo", "status", "--format", "json"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert [s["commit_sha"] for s in listed] == [source.head_sha]


def test_bad_locator_is_a_usage_error_not_an_acquisition_failure(
    wired: CliServices, capsys: pytest.CaptureFixture[str]
) -> None:
    """A typo is exit 2; only a real fetch problem is exit 3."""
    assert run(wired, ["repo", "fetch", "ext::sh -c evil"]) == 2
    assert "invalid repository locator" in capsys.readouterr().err


def test_local_path_requires_the_opt_in_flag(
    wired: CliServices, source: FixtureRepo, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(wired, ["repo", "fetch", source.locator]) == 2
    assert "allow-local-path" in capsys.readouterr().err


def test_unknown_ref_exits_three(
    wired: CliServices, source: FixtureRepo, capsys: pytest.CaptureFixture[str]
) -> None:
    code = run(
        wired,
        ["repo", "fetch", source.locator, "--allow-local-path", "--ref", "no-such-branch"],
    )
    assert code == 3
    assert capsys.readouterr().err


def test_snapshot_survives_in_the_database_across_connections(
    wired: CliServices, source: FixtureRepo, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run(wired, ["repo", "fetch", source.locator, "--allow-local-path", "--quiet"])
    capsys.readouterr()

    reopened = connect(tmp_path / "workspace" / "issuepilot.db")
    try:
        rows = reopened.execute("SELECT commit_sha FROM rep_snapshots").fetchall()
        assert [row["commit_sha"] for row in rows] == [source.head_sha]
    finally:
        reopened.close()
