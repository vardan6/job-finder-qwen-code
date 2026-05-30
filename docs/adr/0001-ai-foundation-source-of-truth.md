# ADR 0001: AI Foundation Source of Truth

## Status

Accepted

## Context

`job-finder` has a legacy LLM provider and chat setup that is older and not a
good base for the desired AI chat and AI agent experience.

`remote-rover/gcs_server` already contains a stronger AI foundation:

- polished provider settings UX
- purpose-based routing
- session-based AI chat
- agent/tool runtime
- provider capabilities and auth modes
- persisted AI session storage

The goal is to bring those strengths into `job-finder` without introducing any
runtime dependency on `remote-rover` and without carrying rover-specific
surfaces into this repository.

This ADR closes the completed grilling session and records the chosen
architecture direction.

## Decision

`job-finder` will adopt a copied-and-adapted AI foundation derived from
`remote-rover/gcs_server` as its new canonical AI architecture.

The decision has these concrete parts:

1. Replace the legacy `job-finder` LLM provider setup rather than preserving it
   as a parallel system.
2. Copy implementation patterns and code structure from `remote-rover` into
   `job-finder`; do not call into `remote-rover` at runtime.
3. Use the `remote-rover` provider settings model as the canonical LLM
   configuration system in `job-finder`.
4. Use the `remote-rover` session-based AI chat model as the canonical chat
   model in `job-finder`.
5. Keep both `Chat` and `Agent` modes visible in phase 1.
6. Make `Agent` mode a real tool-calling mode from day one, but start with a
   narrow job-finder-specific tool catalog.
7. Keep sessions as the primary AI unit. Sessions are general by default and
   may optionally attach a candidate.
8. Preserve purpose-based routing with the initial `job-finder` purpose set:
   - `general_chat`
   - `agent`
   - `document_analysis`
   - `candidate_analysis`
   - `job_matching`
9. Preserve provider auth modes and capabilities from the copied model.
10. Exclude rover-specific tools, planning-shell concepts, replay/map
    surfaces, and rover-specific terminology.

## Consequences

### Positive

- One canonical AI system instead of a dual-track setup
- Faster path to a polished AI settings page and multi-session AI chat
- Stronger base for future job-finder-specific agent tools
- Cleaner migration path for existing AI-backed features

### Negative

- The migration is more invasive than a UI-only port
- Existing legacy provider/model code will need replacement or retirement
- Some final details remain adjustable until the first visible GUI milestone is
  proven in code

## Rejected alternatives

### Keep the old `job-finder` provider/model system and only restyle the UI

Rejected because it would preserve the wrong backend shape and likely force a
second migration later.

### Maintain two AI systems in parallel during the migration

Rejected because chat, agent, and other AI-backed features would then resolve
through different sources of truth.

### Introduce a separate candidate “workspace” object as the primary unit

Rejected because the primary unit should be the AI session. Candidate context
can be attached to a session when needed.

### Import rover-specific tools and planning/graph surfaces

Rejected because the copied architecture must be adapted to `job-finder`, not
transport domain-specific rover behavior.

## Related documents

- `docs/design/ai-foundation-migration.md`
- `activeContext.md`
- `roadmap.md`
