"""The service surface the CLI is wired with.

The CLI never constructs adapters or facades itself — ``bootstrap`` builds a
``CliServices`` and injects it into ``create_app``. This keeps the CLI a pure
driving adapter: parse arguments, call one service, render the result.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from issuepilot.shared_kernel.cancellation import CancellationToken
from issuepilot.shared_kernel.hashing import Json


@dataclass(frozen=True, slots=True)
class CheckResult:
    """Outcome of one environment check run by ``issuepilot doctor``."""

    name: str
    ok: bool
    detail: str
    remediation: str | None = None


type EnvironmentCheck = Callable[[], CheckResult]


@dataclass(frozen=True, slots=True)
class CliServices:
    version: str
    cancellation: CancellationToken
    environment_checks: Sequence[EnvironmentCheck]
    config_dump: Mapping[str, Json]
    """Effective non-secret configuration, already redacted, for ``config show``."""
