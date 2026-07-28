# ADR-003: Python 3.13 pinned via uv; 3.14 as a CI canary

Status: accepted (2026-07-28)

## Context

The development machine ships Homebrew Python 3.14. The dependency tree
(pydantic-core, numpy, and — from v0.2 — MLflow's large transitive tree)
historically trails new CPython releases, and mypy `--strict` semantics
around PEP 649 lazy annotations were still settling on 3.14. 3.14's headline
features (free-threading, subinterpreters) buy this project nothing.

## Decision

- uv manages the interpreter: `uv python install 3.13`, pinned in
  `.python-version`, `requires-python = ">=3.13"`, committed `uv.lock`.
- The Homebrew interpreter is never on the project's path.
- Toolchain: uv + hatchling (src layout), ruff (lint + format),
  mypy `--strict` over `src` **and** `tests` (fakes are type-checked against
  the same Protocols as real adapters), import-linter for architecture,
  pytest + hypothesis, Typer for the CLI, `just check` as the local gate.
- CI runs a 3.14 job with `continue-on-error: true` as an early-warning
  canary; promotion to 3.14 is a v0.3 decision based on its history.

## Consequences

- One deterministic environment per checkout; no system-Python drift.
- MLflow risk is additionally contained behind `ExperimentTrackerPort` as an
  optional extra with lazy import (v0.2).
