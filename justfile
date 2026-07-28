# Developer entry points. `just check` is the gate before every commit.

default: check

# The full fast gate: lint, types, architecture, default test suite.
check: lint typecheck arch test

lint:
    uv run ruff check .
    uv run ruff format --check .

typecheck:
    uv run mypy

arch:
    uv run lint-imports

# Fast default suite: unit + property + contract(fakes) + security + arch.
test:
    uv run pytest

# Adds real SQLite/git and full-CLI tests.
test-integration:
    uv run pytest -m "integration or e2e"

# Requires a live Ollama daemon with the configured models pulled.
test-ollama:
    uv run pytest -m ollama

# Everything except live-model tests, with the coverage gate.
test-all:
    uv run pytest -m "not ollama" --cov --cov-report=term-missing

fmt:
    uv run ruff format .
    uv run ruff check --fix .
