"""Configuration loading and validation.

Sources, highest precedence first: environment variables
(``ISSUEPILOT_<SECTION>__<KEY>``), an explicit ``--config`` path, then
``./issuepilot.toml``, then the platform config directory. No secrets belong
in this file; ``config show`` renders the redacted effective configuration.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import platformdirs
from pydantic import BaseModel, Field, ValidationError
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

from issuepilot.shared_kernel.errors import UsageError
from issuepilot.shared_kernel.hashing import Json, canonical_json_hash

APP_NAME = "issuepilot"


class ModelsConfig(BaseModel):
    chat: str = "qwen3"
    embedding: str = "embeddinggemma"
    ollama_url: str = "http://127.0.0.1:11434"
    keep_alive: str = "10m"


class RepositoryConfig(BaseModel):
    history_depth: int = Field(default=100, ge=1)
    include_submodules: bool = False
    include_lfs: bool = False
    max_total_bytes: int = Field(default=1_073_741_824, ge=1)
    max_file_bytes: int = Field(default=1_048_576, ge=1)


class RetrievalConfig(BaseModel):
    lexical_candidates: int = Field(default=40, ge=1)
    semantic_candidates: int = Field(default=40, ge=1)
    final_candidates: int = Field(default=12, ge=1)
    chunker_version: str = "1"


class InvestigationConfig(BaseModel):
    strategy: str = "react"
    max_steps: int = Field(default=12, ge=1)
    timeout_seconds: int = Field(default=600, ge=1)
    max_context_tokens: int = Field(default=16_000, ge=1)


class ExecutionConfig(BaseModel):
    enabled: bool = False
    network: str = "off"


class TelemetryConfig(BaseModel):
    local_traces: bool = True
    anonymous_usage: bool = False


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ISSUEPILOT_",
        env_nested_delimiter="__",
        toml_file=None,
    )

    models: ModelsConfig = ModelsConfig()
    repository: RepositoryConfig = RepositoryConfig()
    retrieval: RetrievalConfig = RetrievalConfig()
    investigation: InvestigationConfig = InvestigationConfig()
    execution: ExecutionConfig = ExecutionConfig()
    telemetry: TelemetryConfig = TelemetryConfig()
    workspace_dir: Path = Field(default_factory=lambda: Path(platformdirs.user_data_dir(APP_NAME)))

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            TomlConfigSettingsSource(settings_cls),
        )


def config_search_paths() -> list[Path]:
    return [
        Path.cwd() / "issuepilot.toml",
        Path(platformdirs.user_config_dir(APP_NAME)) / "issuepilot.toml",
    ]


def load_config(explicit_path: Path | None = None) -> AppConfig:
    """Load and validate configuration; raises a typed UsageError on failure."""
    if explicit_path is not None:
        if not explicit_path.is_file():
            raise UsageError(
                f"config file not found: {explicit_path}",
                remediation="pass an existing file or omit --config to use defaults",
            )
        toml_file: Path | None = explicit_path
    else:
        candidates = [p for p in config_search_paths() if p.is_file()]
        toml_file = candidates[0] if candidates else None

    try:
        return _config_class_for(toml_file)()
    except ValidationError as exc:
        raise UsageError(
            f"invalid configuration: {exc}",
            remediation="fix the listed fields in issuepilot.toml or the environment",
        ) from exc


def _config_class_for(toml_file: Path | None) -> type[AppConfig]:
    """The TOML source path lives in class-level model_config, so a per-call
    file requires a dynamic subclass (the pattern pydantic-settings documents)."""
    if toml_file is None:
        return AppConfig

    class _FileConfig(AppConfig):
        model_config = SettingsConfigDict(
            env_prefix="ISSUEPILOT_",
            env_nested_delimiter="__",
            toml_file=toml_file,
        )

    return _FileConfig


def redacted_dump(config: AppConfig) -> dict[str, Json]:
    """Effective configuration as plain JSON data (nothing secret is stored)."""
    dumped = cast("dict[str, Json]", config.model_dump(mode="json"))
    return dumped


def config_hash(config: AppConfig) -> str:
    """Stable hash of the effective configuration, for run lineage."""
    return canonical_json_hash(redacted_dump(config))
