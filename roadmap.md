# Roadmap

Phase 9 is organized as three parallel threads (restructured 2026-07-19;
prior sequential order + rationale in
`docs/reviews/roadmap-reorder-2026-07-19.md`). Slices are ordered
top-to-bottom *within* a thread; threads are independent and non-blocking —
pick the next unchecked slice from any thread. AFK = can run autonomously,
HITL = needs maintainer decision/review. Requirements:
`docs/requirements/product-vision.md`; design: `docs/design/`.

## Delivery order

The remaining work is ordered for execution, not by the legacy phase numbers
used in older history: **9.5 core polish → 10 AI runtime, capability, and
efficiency → 11 additional platforms → 12 accounts and multi-user → 13
accessibility.** Complete a phase's required dependencies before selecting a
later phase; within a phase, use the checklist dependencies and `/next-slice`.

## Phase 9 — Product Completion (complete, branch `stabilize/cleanup-foundation`)

Done so far: gap audit (`docs/reviews/gap-audit-2026-07-19.md`), scoring +
provenance decisions (`docs/design/scoring-and-provenance.md`), Q8 decided →
groundwork-now (2026-07-19).

Threads touch disjoint code: T1 = profile pages/templates/cards (complete),
T2 = models/scoring/search/results (complete), T3 = scraper/login (complete
for LinkedIn; multi-platform expansion deferred, see Phase 11). Closed
2026-07-21 on maintainer basic live-testing of the LinkedIn probe;
comprehensive testing is deferred to later and does not block closure.

### Thread T1 — Profile & UI (maintainer's top pain) — complete

All slices done: card pre-review, app-wide UI/UX cross-comparison, unified
profile-page card pattern, provenance (extraction-occurrence table +
extracted-vs-edited badges), content-aware file-type classification.
Details in `progress.md` (2026-07-19 entries).

### Thread T2 — Data model & search pipeline — complete

Contracts: `docs/design/scoring-and-provenance.md` (score),
`docs/design/remote-verification.md` (R6),
`docs/design/search-runs-and-lists.md` (R7/R11).

All slices done: future-Phase-12 ownership groundwork, deterministic + skills-overlap
+ LLM-refinement scoring, LLM remote-status verification, results-table
upgrade, saveable named search lists, result curation (P4), application
pipeline UI (P1), on-demand re-search diff (P3), per-job tailored
resume/cover letter (P2). Details in `progress.md` (2026-07-19 / 2026-07-21
entries).

### Thread T3 — Platforms & scraping — complete for LinkedIn

- [x] AFK R4: platform research doc in `docs/research/` ranking job platforms
      (informs R3 scope and platform priorities)
- [x] HITL R3: LinkedIn login reliability rework — session-validity probe,
      stateful login UI, visible failure reasons, guided re-login; includes
      pre-search login health probe (P5)
      (design: `docs/design/linkedin-login-reliability.md`; D1-D4 implemented
      and test-covered; maintainer validated D4's probe button live 2026-07-21
      via basic testing — comprehensive testing deferred, non-blocking)

Additional platforms (WWR and beyond) are deliberately deferred — see
Phase 11 below.

## Phase 9.5 — Stabilization polish, LinkedIn-first (active, branch `stabilize/cleanup-foundation`)

Maintainer priority after Phase 9 closure (2026-07-21): polish the core,
single-platform (LinkedIn-only) product end-to-end and its existing
single-user chat/settings shell — scraper/search reliability and overall UX —
before starting the following delivery phases. Use `/next-slice` to pick up
one unchecked slice at a time.

- [x] AFK — location-default persistence fix: a submitted search location now
      persists to a dedicated `CandidatePreferences.last_search_location`
      field (not `candidate.location`, so search tuning never rewrites
      profile data) via `_persist_search_location` in `routes/jobs.py`,
      called from all three search-start endpoints; `GET` search-config
      prefers it over `candidate.location`. Migration:
      `migrate_search_location` in `database.py`. Tests:
      `test_search_location_persistence.py`. 241/241 tests pass.
- [ ] Broader UX polish pass on the LinkedIn-only search/results/apply
      flow — scope to be defined by the maintainer.
- [x] AFK — Preferred-title review reliability, extraction quality, and
      title-route profile isolation (all complete). Details in `progress.md`
      (2026-07-21 entries). Contract: `docs/design/scoring-and-provenance.md`.

### Chat and settings shell polish (former Phase 7)

These are product-polish slices, not a separate remote-rover-parity goal.
They may be selected alongside the LinkedIn flow work when they are the
smallest valuable next change.

All 6 slices done: provider registry Cancel-edit control, chat session
inline rename + Markdown transcript export, trace/diagnostics open-state
persistence, dark/light theme toggle, portable settings export/import
(`routes/ai_settings.py`), and the `/settings/tools` discovery page. Details
in `progress.md` (2026-07-21 entries).

## Phase 10 — AI runtime, capability & efficiency (deferred)

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
