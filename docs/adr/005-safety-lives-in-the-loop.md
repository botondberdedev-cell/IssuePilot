# ADR-005: Safety properties live in the loop, not in the prompt

Status: accepted (2026-07-28)

## Context

An agent that reads untrusted repositories has two failure modes that look
similar from the outside: the model does something unsafe because it was
confused, and the model does something unsafe because the repository told it
to. Prompt text can discourage both. It cannot prevent either — a prompt is a
request, and the model is free to decline.

## Decision

Every property that must hold regardless of model behaviour is enforced in
the ReAct loop or the domain, and the prompt only *explains* it:

| Property | Where it is enforced |
|---|---|
| Only known tools run | `ToolName` is a closed enum; an unrecognized name is never dispatched |
| Runs terminate | `StepBudget` is an immutable domain object that cannot go negative |
| Reads stay in the snapshot | `resolve_within` fully resolves symlinks and checks containment |
| Reads are bounded | The loop caps the requested line range before reading |
| Evidence is real | Citations are re-verified against the snapshot before the report is built |
| Claims need evidence | `Finding.__post_init__` refuses a factual claim with no reference |
| Evidence belongs to this run | `InvestigationReport.__post_init__` rejects a foreign commit SHA |
| Search text is inert | FTS5 terms are extracted and quoted as literal phrases |

Retrieved repository content enters the prompt as quoted observation data
under a heading that names it as data. A file instructing the model to use a
different tool changes nothing, because the tool table is not consulted from
the prompt.

## Consequences

- The unit tests for these properties script *hostile* model transcripts — an
  invented tool, a traversal path, an out-of-range citation — and assert the
  loop constrains each. They do not depend on a model being available, so
  they run on every commit.
- A prompt change cannot weaken a safety property, which means prompts can be
  iterated on freely during v0.2 evaluation work.
- The cost is that the loop contains logic a "just ask the model" design
  would not need. That is the intended trade.
