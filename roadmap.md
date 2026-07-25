# Roadmap

Remaining work only. Completed phases are listed at the bottom with detail in
`progress.md`. AFK = can run autonomously, HITL = needs maintainer
decision/review. Requirements: `docs/requirements/product-vision.md`; design:
`docs/design/`.

## Delivery order

Ordered for execution, not by the legacy phase numbers used in older history:
**10 AI runtime, capability, and efficiency → 11 additional platforms → 12
accounts and multi-user → 13 accessibility.** Phases 9 and 9.5 are complete
(branch `stabilize/cleanup-foundation`). Complete a phase's required
dependencies before selecting a later phase; within a phase, use the checklist
dependencies and `/next-slice`.

## Phase 10 — AI runtime, capability & efficiency (next)

Design canon: `docs/design/ai-agent-graph.md` (loop stages + per-stage status
table), `docs/design/agent-provider-capabilities.md`, and
`docs/design/ai-llm-efficiency-audit.md`; full agent decomposition in
`history/ai-agent-architecture-review-2026-06-04.md`. Today `run_mode=agent`
is a placeholder (one plain completion + synthetic trace events, no tools
bound). Phase 10 combines the former Phase 6 and Phase E because they share
the LLM call path and compact-context dependency.

### Shared LLM runtime foundation

These improvements benefit both lightweight chat/parser models and future
tool-capable agent models; they do not require tool calling.

- [x] 10.1-10.4 AFK — Ollama `keep_alive=-1`, config-driven `max_output_tokens`
      caps, verified LiteLLM HTTP client reuse (no code change needed), and
      `json_mode`/`response_format` with capability-probe fallback for parser
      call sites. All complete, 239/239 tests pass. Details in `progress.md`
      (2026-07-21 entry).

### Agentic runtime

Agent mode must use a verified tool-capable model. A lightweight model that
lacks tools remains eligible for plain chat; it is never forced through the
agent loop.

- [x] Typed read-only tool definitions for `list_data_surfaces` and
      `candidate_skills_lookup`.
- [ ] 10.5 HITL — Capability gate + visible fallback: per-model *verified*
      tool-calling probe, route past no-tools models, visibly degrade to plain
      chat on a runtime tools-unsupported error, and persist that finding.
      Needs provider validation; contract:
      `docs/design/agent-provider-capabilities.md`.
- [ ] 10.6 AFK — Minimal real loop end-to-end (depends on 10.5): bind existing
      typed tools to the model for `run_mode=agent`, single tool round-trip
      (validate args → execute → feed result back once), and emit a **real**
      trace event. Stop reasons `final_answer` /
      `tool_call_validation_failed` / `tool_execution_failed`.
- [ ] 10.7 AFK — Full iteration + guards (depends on 10.6): loop to
      `max_iterations`, detect repeated failures, and stop with
      `iteration_limit` / `repeated_tool_failure`.
- [ ] 10.8 AFK — Compact `AIContextService` + `list_data_surfaces` manifest
      (depends on 10.6): move context out of `routes/chat.py`, stop eager
      candidate injection in agent mode, and load deeper data lazily via tools.
- [ ] 10.9 AFK — Persisted trace store + `policy_engine` (depends on 10.7):
      replace synthetic events; enforce permission class / scopes /
      side-effects with redaction.
- [ ] 10.10 AFK — Expand the typed read-tool catalog and add approval-in-loop
      for write tools (depends on 10.9).

### Context-aware efficiency & visibility

- [ ] 10.11 AFK — Provider-aware prompt caching (depends on 10.8): Anthropic
      `cache_control` breakpoints on a byte-stable system/context prefix;
      provider-native caching for OpenAI/Gemini where available.
- [ ] 10.12 AFK — Optional Redis-backed response/semantic cache for repeated
      analytical calls (`REDIS_URL` already exists in config).
- [ ] 10.13 AFK — Aggregate token/cost and cache-hit telemetry for visibility.

The only open design point is 10.11's cached-prefix stability (per-provider
minimum-token thresholds and byte stability). Resolve it when 10.8/10.11 is
selected; escalate to `/grill-me` only if contentious.

## Phase 11 — Additional platforms (deferred)

Begins only after Phase 9.5. Ranking/rationale:
`docs/research/job-platform-ranking-2026-07-19.md` (We Work Remotely ranked
next, then Remote OK). Current WWR adapter
(`job-finder-web/backend/scrapers/we_work_remotely.py`) is a fixture-based
parser stub only — live navigation raises `NotImplementedError`. A fresh design
pass must establish login/session-health reuse, regional eligibility handling,
and apply-handoff before implementation.

- [ ] HITL — design review for multi-platform login/session contract
      (generalizing the LinkedIn probe pattern)
- [ ] HITL — implement We Work Remotely live search + session health per
      research doc scope
- [ ] Future — Remote OK feed adapter (after WWR)

## Phase 12 — Accounts & Multi-User (end-state; R8–R10)

Groundwork lives in Phase 9 Thread T2. This remains deliberately last. R10
(profile visibility status) and R9 (profiles-per-user UX) are done — details
in `progress.md`.

- [ ] HITL R8: real auth — registration, login, sessions, per-user isolation
      (sweep the retrofit inventory in `docs/design/ownership-groundwork.md`
      onto `get_owned_candidate`)
- [ ] HITL R8: account-type behavior/UI (job-seeking vs job-providing) —
      schema discriminator already lands in T2 groundwork
- [ ] Future R8: employer/recruiter side — search/match public profiles
      (explicitly deferred; keep models compatible)

## Phase 13 — Optional accessibility

- [ ] TTS support (browser speech and/or local service integration)

## Completed (details in `progress.md`)

- [x] Phase 0 — Workflow bootstrap
- [x] Phase 1 — AI foundation (providers, sessions, streaming chat, routing)
- [x] Phase 2 — Agent expansion (tool surfaces, approval-aware mutations)
- [x] Phase 3 — UX consolidation (chat shell alignment)
- [x] Phase 4 — Remote-rover parity P0 (fallback editor, quick actions, stop-stream, archived sessions)
- [x] Phase 5 — Remote-rover parity P1 (run modes, slash commands, traces, diagnostics, recovery)
- [x] Phase S — Stabilization intake (enhance-not-recreate, handoff archive,
      vision capture, gap audit; inline-JS extraction folded into Thread T1)
- [x] Phase 9 — Product Completion (closed 2026-07-21): T1 profile/UI, T2 data
      model & search pipeline, T3 LinkedIn login-reliability rework +
      platform-ranking research. Contracts in `docs/design/`
      (scoring-and-provenance, remote-verification, search-runs-and-lists,
      linkedin-login-reliability); multi-platform expansion deferred to
      Phase 11
- [x] Phase 9.5 — Stabilization polish, LinkedIn-first (closed 2026-07-24):
      search-location persistence, preferred-title reliability + title-route
      profile isolation, chat/settings shell polish (former Phase 7, all 6
      slices); broader UX polish closed as covered by cumulative Phase 9/9.5
      work
