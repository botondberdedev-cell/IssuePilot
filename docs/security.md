# Security model

Everything below describes controls that exist in the code today, each with
the test that holds it in place. Planned-but-unbuilt controls are listed
separately at the end so this document cannot be mistaken for a claim of
completeness.

## Trust boundaries

| Input | Trust | Why |
|---|---|---|
| CLI arguments | Trusted | The user typed them |
| `issuepilot.toml` | Trusted | The user wrote it; it holds no secrets |
| Repository content | **Untrusted** | Anyone can put anything in a repository |
| Model output | **Untrusted** | Schema-constrained, but semantically unconstrained |
| Ollama daemon | Trusted | Runs locally, under the user's control |

The two untrusted inputs meet each other inside the agent loop, which is why
the loop is where enforcement lives (see ADR-005).

## Controls

### Repository acquisition

`RepositoryLocator.parse` is a security boundary: everything it accepts is an
explicit decision.

- Rejected: `git://` (unauthenticated), `ftp://`, `ext::` and remote helpers
  (arbitrary command execution), `file://`, plain `http://`, embedded
  credentials, control characters, and any locator starting with `-`.
- Local paths require `--allow-local-path`.
- Git runs through argument arrays, never a shell, with user-controlled values
  passed after `--end-of-options` so a value shaped like a flag cannot become
  one.
- `GIT_TERMINAL_PROMPT=0`, so a run can never block on a hidden prompt.

*Tests:* `tests/security/test_locator_security.py` (16-case hostile matrix),
`tests/unit/repository/test_values.py`, `tests/property/test_repository_props.py`
(parsing never raises anything but `ValueError`).

### Credentials

IssuePilot never reads, stores, or transmits credentials. SSH authentication
is delegated entirely to the user's existing agent and `~/.ssh/config`; HTTPS
to git's credential helper. There is no `--token` flag, deliberately, so a
secret cannot land in shell history or a process listing.

Log output is redacted as a last line of defense: URL userinfo, GitHub and AWS
token shapes, bearer headers, and private-key blocks.

*Tests:* `tests/security/test_redaction.py`.

### Snapshot confinement

Repository content can contain symlinks pointing anywhere. Every read fully
resolves its path and verifies the result is still inside the snapshot root.

A subtle point: `contains()` reports an escaping path as *absent* rather than
raising, so an existence check cannot be used as an oracle for files outside
the snapshot.

*Tests:* `tests/security/test_snapshot_confinement.py`.

### Secrets in the repository

`.env*`, `*.pem`, `*.key`, SSH private keys, and credential exports are
excluded by the eligibility policy *before* indexing, so they never reach an
embedding model or a report. Secret detection runs ahead of the size and
binary checks, so an oversized `.env` is reported as a secret rather than as
a size problem.

*Tests:* `tests/unit/repository/test_manifest.py`.

### Query injection

FTS5 has its own query syntax, and query text arrives from the issue statement
and from model tool calls. Terms are extracted and quoted as literal phrases,
so `NOT`, `*`, column filters, and unbalanced quotes are treated as text.

*Tests:* the hostile-query matrix in `tests/contract/test_lexical_index_port.py`,
run against both the fake and real FTS5.

### Agent containment

- Tools are a closed enum; an invented name is refused, not dispatched.
- The step budget is a domain object that cannot go negative.
- Read ranges are capped.
- Evidence from another snapshot is discarded.
- A claim citing nothing becomes explicit speculation.

*Tests:* `tests/unit/investigation/test_react_strategy.py`,
`tests/unit/investigation/test_run_investigation.py`.

### Execution

v0.1 never executes repository code. Sandboxed, allow-listed test execution is
designed as an opt-in port and deferred to v0.3 (ADR-002).

## Resource limits

- **Per-file size cap** (`repository.max_file_bytes`): oversized files are
  excluded from the manifest with a recorded reason.
- **Total analyzable size** (`repository.max_total_bytes`): enforced while the
  manifest is built, so the first file that pushes the running total past the
  limit stops the work. Only analyzable bytes count — a large binary that was
  never going to be read is free.
- **Step budget** (`investigation.max_steps`): a domain object that cannot go
  negative, so a loop terminates by construction.
- **Wall-clock budget** (`investigation.timeout_seconds`): bound to a single
  clock, so the loop cannot check a deadline against a different clock than
  the one that started it. Running out of time ends the run and marks the
  report incomplete rather than discarding the evidence already gathered.
- **History depth** (`repository.history_depth`) bounds how much git fetches.
- An inter-process lock prevents concurrent runs from racing on a shared
  object cache.

## Known gaps

Honest accounting of what is *not* yet built:

- **Prompt-injection resistance is untested end to end.** The controls exist
  and are unit-tested, but there is no fixture repository containing an
  injection payload driven through a real model. That is a v0.2 evaluation
  case.
- **Content scanning is name-based.** A secret in a file without a
  secret-looking name will be indexed.
- **No signature verification** of fetched objects.

## Reporting

This is a personal project without a security team. Open an issue for
anything found here.
