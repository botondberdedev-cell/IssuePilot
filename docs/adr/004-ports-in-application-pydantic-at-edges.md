# ADR-004: Ports live in application/; Pydantic only at the edges

Status: accepted (2026-07-28)

## Context

Two recurring hexagonal-architecture decisions needed a single, enforceable
answer: where port interfaces live, and whether the domain may use Pydantic.

## Decision

**Ports are `typing.Protocol`s in each context's `application/ports.py`.**
The domain stays pure computation (entities, value objects, deterministic
services); ports name I/O concerns and are shaped by use cases, which is the
application layer's job. Consequence, accepted deliberately: logic that needs
a port is an application service, never a domain service.

**Domain and application layers use `@dataclass(frozen=True, slots=True)`
with `__post_init__` validation, stdlib only.** Pydantic v2 appears
exclusively at the edges: `bootstrap/config.py` (pydantic-settings) and
infrastructure modules parsing external JSON/YAML (Ollama structured outputs,
dataset files). The checked-in `prompts/*.schema.json` files are the source
of truth for model-output schemas; infrastructure may mirror them as Pydantic
models, with a test asserting `model_json_schema()` matches the file.

Both rules are enforced by import-linter (contracts 3 and 4 forbid
`pydantic` in domain and application layers), not by convention. The
conventions arch test additionally requires every declared port to have a
registered fake and a contract suite, so fakes and real adapters cannot
drift apart silently.

## Consequences

- Domain invariants (which are relational, constructor-level rules) stay
  free of framework churn and import cost.
- A handful of hand-written mappings from validated JSON into dataclasses
  exist in infrastructure; contract tests concentrate exactly there.
