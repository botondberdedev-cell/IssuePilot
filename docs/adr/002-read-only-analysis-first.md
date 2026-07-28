# ADR-002: Read-only analysis before patch generation

Status: accepted (2026-07-28)

## Context

Cloned repository content is untrusted input. An agent that executes
repository code (or generates and applies patches) multiplies the attack
surface: arbitrary code execution, prompt injection escalating to tool
escalation, and credibility damage from confidently wrong changes.

## Decision

Version 1 never executes repository code and never modifies the target
repository. The product promise is narrower and verifiable: *given a
repository and a problem statement, produce a reproducible investigation with
claims tied to exact files, line ranges, and a commit SHA*. The core
invariant is enforced in the domain (`investigation/domain/report.py`): a
factual finding cannot exist without verified evidence pinned to the run's
snapshot commit; unverifiable statements survive only as explicitly marked
speculation.

Sandboxed, allow-listed test execution is designed as an opt-in port
(`adapters/sandbox`, feature-flagged, default off) and deferred to v0.3.

## Consequences

- Exit code 5 ("finished but did not meet evidence requirements") is a
  first-class outcome — the tool refuses to invent.
- The evaluation dataset can score citation validity deterministically.
- Patch generation later builds on verified evidence rather than replacing it.
