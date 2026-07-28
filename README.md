# IssuePilot Local

A local-first CLI that takes a Git repository, a ref, and an issue statement, and produces an
evidence-linked engineering investigation: every claim cites exact files, line ranges, and a
pinned commit SHA. Inference runs locally through Ollama. The tool never executes repository
code.

> Status: pre-release scaffolding (v0.1.0-dev). See `docs/adr/` for architecture decisions.

## Development

```bash
uv sync          # create the environment (Python 3.13, pinned via .python-version)
just check       # ruff + mypy --strict + import-linter + fast test suite
```

Test tiers: plain `pytest` runs the fast default set (unit, property, contract-with-fakes,
security, arch). `pytest -m integration` adds real SQLite/git; `-m e2e` drives the CLI;
`-m ollama` requires a live Ollama daemon.

## License

Apache-2.0
