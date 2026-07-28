# IssuePilot

A local-first CLI that investigates a repository issue and produces an
**evidence-linked report**: every claim cites an exact file, line range, and
commit SHA. Inference runs on your machine through Ollama. The tool reads
repositories; it never executes them.

```bash
issuepilot investigate git@github.com:example/payments.git \
  --issue "Refunds remain pending after a webhook retry"
```

```
Refund retries can leave the state transition uncommitted.
commit 4f2a7c1b9e83...  (complete)

1. The retry path returns before the transition commits.
   confidence 0.80
   evidence: src/refunds/webhook.py:84-121 @ 4f2a7c1b9e83
   evidence: src/refunds/state.py:33-59 @ 4f2a7c1b9e83
```

## Why the citations matter

An LLM asked about code will produce a confident answer whether or not it
looked. IssuePilot's central rule is enforced in the domain, not requested in
a prompt: a factual finding must carry at least one evidence reference that
**resolves in the pinned snapshot**, or it is marked speculation. The model
proposes; the code decides what may be cited.

That makes reports checkable. Every citation names a commit, so you can open
the exact lines the tool read — even after the branch has moved on.

## Install

Requires [uv](https://docs.astral.sh/uv/), git, and
[Ollama](https://ollama.com).

```bash
uv sync
ollama pull qwen3:8b
ollama pull embeddinggemma
uv run issuepilot doctor
```

`doctor` checks git, SQLite FTS5, the Ollama daemon, the exact model tags,
and workspace writability, and tells you how to fix whatever is missing.

## Commands

| Command | What it does |
|---|---|
| `investigate <repo> --issue …` | Investigate and produce a cited report |
| `repo inspect <repo>` | Map the repository: languages, file counts, why files were skipped |
| `index <repo>` | Build the searchable index |
| `search <repo> <query>` | Hybrid lexical + semantic search |
| `runs` | List previous investigations |
| `doctor` | Check the environment |

Issue text comes from `--issue`, `--issue-file path`, or `--issue-file -` for
stdin. Every command supports `--format terminal|markdown|json`; JSON is a
stable, versioned contract suitable for piping into other tools.

## How it works

1. **Acquire.** Fetch the requested ref into a shared bare object cache,
   resolve it to a full commit SHA, and materialize a detached snapshot,
   published by a single atomic rename. From there the SHA is the identity;
   the branch name is only provenance.
2. **Index.** Chunk eligible files deterministically — Python by top-level
   definition, Markdown by heading, everything else by overlapping line
   windows — into SQLite FTS5 and a memory-mapped vector index.
3. **Investigate.** A bounded ReAct loop searches, reads, and records
   hypotheses within a step budget.
4. **Report.** Claims are checked against evidence that still resolves in the
   snapshot before anything is written.

Lexical search works with no model running, so the tool stays useful when
Ollama is down and retrieval can be evaluated independently of the embedder.

## Safety

Cloned code is untrusted input, and the controls live in code rather than in
prompt text:

- **Transport allowlist.** `git://`, `ext::`, embedded credentials, and
  argument-shaped locators are rejected before any git process exists.
- **Confinement.** Every read resolves symlinks and verifies the result is
  still inside the snapshot, so a repository cannot make the tool read — and
  then cite, lending false authority to — files elsewhere on your machine.
- **Closed tool set.** The agent's tools are an enum. A tool name the model
  invents is refused, not dispatched.
- **Prompt injection.** Repository text enters prompts as quoted observation
  data. A README saying "ignore your instructions" cannot add tools or change
  policy, because policy is enforced in the loop.
- **Secrets.** `.env` files, private keys, and credential exports are excluded
  before indexing, so they never reach an embedding model or a report.
- **No execution.** v0.1 never runs repository code.

## Development

```bash
just check
```

Runs ruff, mypy `--strict`, seven import-linter architecture contracts, and
the fast test suite. Slower tiers: `pytest -m integration` (real git and
SQLite), `-m e2e` (full CLI), `-m ollama` (live model).

The architecture is a modular monolith with six bounded contexts whose
boundaries are machine-enforced — a violation fails `just check`, not review.
Every port has a fake and a contract suite that runs both implementations
through identical assertions, so fakes cannot quietly drift from the real
adapters. See [docs/adr/](docs/adr/).

## Status

v0.1 is feature-complete: acquisition, indexing, hybrid retrieval, the ReAct
agent, and cited reports. Next is v0.2 — a versioned evaluation dataset,
quality gates in CI, and MLflow lineage — which is what will let claims about
quality be measured rather than asserted.

Known limitations: the model is poorly calibrated and tends to report high
confidence; evaluation is not yet automated; only Python and Markdown get
structure-aware chunking.

## License

Apache-2.0
