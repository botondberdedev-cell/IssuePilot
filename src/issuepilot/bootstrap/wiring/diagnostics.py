"""Doctor environment checks, assembled from the technology adapters."""

from __future__ import annotations

from issuepilot.adapters.cli.services import CheckResult, EnvironmentCheck
from issuepilot.adapters.git.client import git_version
from issuepilot.adapters.ollama.health import check_health
from issuepilot.adapters.sqlite.connection import connect, has_fts5
from issuepilot.bootstrap.config import AppConfig


def build_environment_checks(config: AppConfig) -> list[EnvironmentCheck]:
    def check_git() -> CheckResult:
        version = git_version()
        if version is None:
            return CheckResult(
                name="git",
                ok=False,
                detail="git executable not found",
                remediation="install git (e.g. `brew install git`) and ensure it is on PATH",
            )
        return CheckResult(name="git", ok=True, detail=version)

    def check_sqlite_fts5() -> CheckResult:
        conn = connect(":memory:")
        try:
            if has_fts5(conn):
                return CheckResult(name="sqlite-fts5", ok=True, detail="FTS5 available")
            return CheckResult(
                name="sqlite-fts5",
                ok=False,
                detail="this Python's SQLite build lacks FTS5",
                remediation="use the uv-managed CPython (uv sync), whose SQLite ships FTS5",
            )
        finally:
            conn.close()

    def check_ollama() -> CheckResult:
        health = check_health(config.models.ollama_url)
        if not health.reachable:
            return CheckResult(
                name="ollama",
                ok=False,
                detail=f"not reachable at {config.models.ollama_url}",
                remediation=(
                    "start the daemon with `ollama serve` (or `brew services start ollama`)"
                ),
            )
        return CheckResult(name="ollama", ok=True, detail=f"{len(health.models)} models available")

    def check_models() -> CheckResult:
        health = check_health(config.models.ollama_url)
        if not health.reachable:
            return CheckResult(
                name="models",
                ok=False,
                detail="cannot verify models while Ollama is unreachable",
                remediation="start Ollama first",
            )
        missing = [
            name
            for name in (config.models.chat, config.models.embedding)
            if not health.has_model(name)
        ]
        if missing:
            return CheckResult(
                name="models",
                ok=False,
                detail=f"missing: {', '.join(missing)}",
                remediation="pull them with " + " && ".join(f"`ollama pull {m}`" for m in missing),
            )
        return CheckResult(
            name="models",
            ok=True,
            detail=f"chat={config.models.chat} embedding={config.models.embedding}",
        )

    def check_workspace() -> CheckResult:
        path = config.workspace_dir
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".doctor-write-probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
        except OSError as exc:
            return CheckResult(
                name="workspace",
                ok=False,
                detail=f"{path} is not writable: {exc}",
                remediation="fix permissions or set a different workspace_dir in issuepilot.toml",
            )
        return CheckResult(name="workspace", ok=True, detail=str(path))

    return [check_git, check_sqlite_fts5, check_ollama, check_models, check_workspace]
