# ADR-001: Local CLI as a modular monolith

Status: accepted (2026-07-28)

## Context

IssuePilot investigates repository issues using local inference (Ollama). The
domain calls for strong boundaries (six bounded contexts), but the product is
a single-user, single-machine tool. Distributed infrastructure would add
operational cost without user value at this stage.

## Decision

One Python process, one package, six bounded contexts as sub-packages
(`repository`, `knowledge`, `investigation`, `evaluation`, `governance`,
`feedback`), each split into `domain/application/infrastructure`. DDD
boundaries are code boundaries, machine-enforced by seven import-linter
contracts that run in CI **and** in the default pytest suite. Cross-context
communication uses IDs, immutable DTOs, and in-process domain events with a
SQLite outbox. `bootstrap/` is the only module that sees more than one
context; consumers reach producers through translator objects wired there.

## Consequences

- Adding a daemon later (`issuepilot serve`, phase v0.3) reuses the same
  application layer; WAL-mode SQLite was chosen from day one for this.
- Every architectural claim in the docs is testable: breaking a boundary
  fails `just check`.
- The cost is ceremony; the mitigation is the stub-with-tests policy —
  a context not on the current milestone's critical path is value objects,
  ports, fakes, and a facade, nothing more.
