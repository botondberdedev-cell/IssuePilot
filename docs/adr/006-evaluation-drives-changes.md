# ADR-006: Retrieval and prompt changes are justified by measurement

Status: accepted (2026-07-28)

## Context

Retrieval quality and prompt wording are the two parts of this system where
intuition is least reliable and most tempting. A single well-chosen demo
question can make either look excellent. Early in this project exactly that
happened: one hand-picked question returned the right file with the right
lines, and the tool appeared to work well.

Run against eight cases, required-path recall was 0.375.

## Decision

No change to retrieval ranking, chunking, or prompt text ships without a
before-and-after number from `issuepilot eval run` on an unchanged dataset.
The dataset hash is recorded with every result, because a comparison across
different cases is not a comparison.

Corollaries:

- The evaluation dataset is versioned data, not test fixtures. It changes in
  its own commits, never alongside a change it is measuring.
- A failing gate is information, not an emergency. The first run against the
  real dataset failed, and that failure is what produced the two fixes below.
- Deterministic metrics only. An LLM judge would make the gate measure
  agreement with a model rather than quality.

## What this produced

The first measured cycle found two defects that manual testing had missed:

*Retrieval answered from prose.* This repository documents its own mechanisms
in ADRs and a security model, and that prose out-competes the code
semantically. Asked what stops the investigation loop running forever, the
tool cited essays about the budget rather than `budget.py`. Fixed by
diversifying results so one verbose file cannot occupy every slot, and by
telling the agent that documentation states intent while code states
behaviour.

*Synthesis invented findings.* When the model concluded nothing, our code
fabricated a placeholder finding — an unfounded claim produced by the very
component meant to prevent them. Fixed by allowing a report with no findings
provided it explains what it could not establish.

recall 0.375 → 0.625, honesty 0.875 → 1.000, pass-rate 0.250 → 0.625.

## Consequences

- Retrieval work has a cost: each idea needs a suite run, which needs a live
  model. That is the intended friction.
- Recall at 0.625 is now the number to beat, and it is published in the
  README rather than described as promising.
