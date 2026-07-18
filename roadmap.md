# Roadmap

Ordered top-to-bottom = execution order (reordered 2026-07-19; rationale in
`docs/reviews/roadmap-reorder-2026-07-19.md`). AFK = can run autonomously,
HITL = needs maintainer decision/review. Requirements:
`docs/requirements/product-vision.md`; design: `docs/design/`.

## Phase 9 — Product Completion (active, branch `stabilize/cleanup-foundation`)

Done so far: gap audit (`docs/reviews/gap-audit-2026-07-19.md`), scoring +
provenance decisions (`docs/design/scoring-and-provenance.md`).

### 9A — Reviews first (cheap, unblock everything)

- [ ] AFK R2 pre-review: behavior-level audit of all profile-page cards
      (fold/unfold, file open, listing, edit flows) — per-card bugs and
      divergences into `docs/reviews/`
- [ ] AFK R2 app-wide UI/UX cross-comparison: inventory patterns (cards,
      tables, edit modes, modals, badges, loading/error states) across all
      pages; findings + target pattern set into `docs/reviews/`
- [ ] AFK R4: platform research doc in `docs/research/` ranking job platforms
      (moved early: informs R3 scope and platform priorities)

### 9B — Model groundwork before new tables (gated on Q8)

- [x] HITL Decide multi-user timing (Q8) → groundwork-now (2026-07-19)
- [ ] AFK Phase-10 groundwork: `User` model + `user_id` on `Candidate` +
      seeded auto-login dev user (no login UI) — lands BEFORE new tables
      below so nothing is migrated twice

### 9C — Profile surface (maintainer's top pain)

- [ ] AFK R2: unify profile-page cards into one shared card pattern
      (skills + preferred titles first; extracts detail.html inline JS as a
      side effect)
- [ ] AFK R1: provenance — persist extracted-vs-edited per title/skill and
      surface badges + reset-to-extracted in the unified cards
- [ ] AFK R1: content-aware file-type classification (resume/CV/other) to
      replace filename-keyword guessing

### 9D — Search → score → present pipeline (dependency chain, in order)

- [ ] AFK R5 slice 1: deterministic title-match scoring + score column
- [ ] AFK R5 slice 2: skills-overlap scoring folded into weighted composite
      (config weights, breakdown data)
- [ ] AFK R6: LLM remote-status verification with contradiction evidence
      (before the table so the table can show verified status)
- [ ] AFK R7 slice 1: results table upgrade — salary/verified-remote/score
      columns, sortable, best-match default order, score breakdown on expand
- [ ] AFK R7 slice 2: saveable named search lists (`SearchRun` model —
      after 9B groundwork), multiple lists, revisit past searches
- [ ] AFK R7: result curation (P4) — hide/dismiss, min-score /
      verified-remote filters, CSV export of a saved list

### 9E — Platform reliability (can interleave with 9C/9D; HITL-heavy)

- [ ] HITL R3: LinkedIn login reliability rework — session-validity probe,
      stateful login UI, visible failure reasons, guided re-login; includes
      pre-search login health probe (P5)
      (needs its own design pass + manual login testing)
- [ ] HITL R3: add next platform per research doc (shared scraper interface)

### 9F — Approved extensions (R11; after 9D)

- [ ] AFK P1: application pipeline UI — status tracking on jobs table using
      existing `JobApplication` model
- [ ] AFK P3: scheduled re-search with "N new since last run" diff
      (builds on 9D saved lists)
- [ ] AFK P2: per-job tailored resume/cover letter via LLM provider system

## Phase 10 — Accounts & Multi-User (end-state; R8–R10)

Groundwork slice lives in 9B. The rest is deliberately last (per maintainer).

- [ ] AFK R10: profile visibility status (`draft`/`private`/`public`) + UI
- [ ] AFK R9: profiles-per-user UX — present candidates as "my profiles"
      (per-track titles, files, searches scoped per profile)
- [ ] HITL R8: real auth — registration, login, sessions, per-user isolation
- [ ] HITL R8: account types (job-seeking vs job-providing) in data model
- [ ] Future R8: employer/recruiter side — search/match public profiles
      (explicitly deferred; keep models compatible)

## Deferred — AI chat/agent track (below product completion)

Resume only when Phase 9 is done or maintainer re-prioritizes. Phase 7 items
overlapping R2 app-wide alignment (sortable tables, theme, layout persistence)
should be folded into 9A/9C slices when those pages are touched, not done twice.

### Phase 6 — Real Agent Runtime

- [ ] Add read-only model-driven agent runtime with typed tools and trace events
  - [x] Typed read-only tool definitions for `list_data_surfaces` and `candidate_skills_lookup`
  - [ ] Compact `AIContextService` for agent mode preserving plain chat behavior
  - [ ] Route `run_mode=agent` through an agent loop for `/api/chat` + `/api/chat/stream`
  - [ ] Enforce provider tool-calling capability/fallback for agent mode

### Phase 7 — Remote-Rover Parity P2 (UX polish)

- [ ] Sortable provider registry table · routing save/reload feedback ·
      cancel-edit flow · inline session rename · copy chat as markdown ·
      trace-block state persistence · layout persistence · JSON settings
      import/export · theme controls · tool discovery surface

### Phase 8 — Optional Accessibility

- [ ] TTS support (browser speech and/or local service integration)

## Completed (details in `progress.md`)

- [x] Phase 0 — Workflow bootstrap
- [x] Phase 1 — AI foundation (providers, sessions, streaming chat, routing)
- [x] Phase 2 — Agent expansion (tool surfaces, approval-aware mutations)
- [x] Phase 3 — UX consolidation (chat shell alignment)
- [x] Phase 4 — Remote-rover parity P0 (fallback editor, quick actions, stop-stream, archived sessions)
- [x] Phase 5 — Remote-rover parity P1 (run modes, slash commands, traces, diagnostics, recovery)
- [x] Phase S — Stabilization intake (enhance-not-recreate, handoff archive,
      vision capture, gap audit; inline-JS extraction folded into 9A/9C)
