# Job Finder Docs

This context defines the project language for documentation intended to guide coding agents and maintainers working on the job-finder repository.

## Language

**Agent-facing documentation**:
Documentation optimized to help coding agents navigate the codebase, preserve invariants, and make safe changes.
_Avoid_: polished prose docs, human-first docs

**Human-facing documentation**:
Documentation optimized for explanation and orientation for maintainers and readers.
_Avoid_: agent operational docs

**Reference input**:
User or domain source material consumed by the product or used to configure candidates.
_Avoid_: architecture docs, specs

**Historical document**:
A preserved snapshot of prior plans, summaries, or notes kept for traceability but not treated as current truth.
_Avoid_: active docs, source of truth

**Requirements**:
The target-state product contract describing the agreed behavior, user expectations, and overall picture of what the project should be when complete.
_Avoid_: implementation details, progress tracking

**Design**:
The implementation contract describing the chosen technical approaches, boundaries, algorithms, and patterns that coding agents should preserve unless explicitly changed.
_Avoid_: feature wishlist, progress tracking

## Relationships

- **Agent-facing documentation** has higher priority than **Human-facing documentation**
- **Reference input** informs the product domain but is not a spec
- **Historical document** may explain past decisions but does not define current behavior
- **Requirements** define the target behavior the product should exhibit
- **Design** constrains how **Requirements** should be implemented
- workflow state files track progress; **Requirements** and **Design** do not

## Example dialogue

> **Dev:** "Should this go into the design doc or the archive?"
> **Domain expert:** "If it helps an agent change the code safely now, it is **Agent-facing documentation**. If it only explains an old implementation pass, it is a **Historical document**."

## Flagged ambiguities

- "documentation" was being used to mean both agent-operational docs and general human-readable docs — resolved: these are distinct, with **Agent-facing documentation** as the primary audience.
- "requirements" versus "status" was ambiguous — resolved: **Requirements** are target-state agreements, while workflow state files carry implementation progress and next-step status.
