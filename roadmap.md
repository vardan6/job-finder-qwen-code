# Roadmap

Phase 9 is organized as three parallel threads (restructured 2026-07-19;
prior sequential order + rationale in
`docs/reviews/roadmap-reorder-2026-07-19.md`). Slices are ordered
top-to-bottom *within* a thread; threads are independent and non-blocking —
pick the next unchecked slice from any thread. AFK = can run autonomously,
HITL = needs maintainer decision/review. Requirements:
`docs/requirements/product-vision.md`; design: `docs/design/`.

## Phase 9 — Product Completion (active, branch `stabilize/cleanup-foundation`)

Done so far: gap audit (`docs/reviews/gap-audit-2026-07-19.md`), scoring +
provenance decisions (`docs/design/scoring-and-provenance.md`), Q8 decided →
groundwork-now (2026-07-19).

Threads touch disjoint code: T1 = profile pages/templates/cards, T2 =
models/scoring/search/results, T3 = scraper/login. One cross-thread edge
exists (T1 slice 4 needs T2 slice 1's groundwork); it is neutralized by
ordering — groundwork is first in T2, provenance fourth in T1, so it never
blocks in practice. Soft touchpoint, not a gate: T2's results-table slice
should adopt the target pattern set from T1 slice 2 if it has landed.

### Thread T1 — Profile & UI (maintainer's top pain)

- [x] AFK R2 pre-review: behavior-level audit of all profile-page cards
      (fold/unfold, file open, listing, edit flows) — per-card bugs and
      divergences into `docs/reviews/`
- [x] AFK R2 app-wide UI/UX cross-comparison: inventory patterns (cards,
      tables, edit modes, modals, badges, loading/error states) across all
      pages; findings + target pattern set into `docs/reviews/`
- [x] AFK R2: unify profile-page cards into one shared card pattern
      (skills + preferred titles first; extracts detail.html inline JS as a
      side effect)
- [x] AFK R1: provenance — extraction-occurrence table (per-file facts) +
      extracted-vs-edited on curated values, badges + reset-to-extracted in
      the unified cards (schema per `docs/design/scoring-and-provenance.md`)
      — new table: requires T2 slice 1 (groundwork) landed first
- [x] AFK R1: content-aware file-type classification (resume/CV/other) to
      replace filename-keyword guessing

### Thread T2 — Data model & search pipeline

Contracts: `docs/design/scoring-and-provenance.md` (score),
`docs/design/remote-verification.md` (R6),
`docs/design/search-runs-and-lists.md` (R7/R11). Groundwork is first here
because it gates every new table in Phase 9 (this thread's `SearchRun`,
T1's extraction-occurrence) — nothing gets migrated twice.

- [x] AFK Phase-10 groundwork per `docs/design/ownership-groundwork.md`:
      `User` model (+ `account_type` discriminator) + `Candidate.user_id`
      (nullable → backfill → NOT NULL) + idempotent seeded auto-login dev user
      (no login UI) + `get_current_user()` / `get_owned_candidate()` contract
      that all new Phase 9 code must use
- [x] AFK R5 slice 1: deterministic title-match scoring + score column +
      ordering-fixture regression tests (aliases, empty descriptions)
- [x] AFK R5 slice 2: skills-overlap scoring folded into weighted composite
      (config weights + alias map, breakdown data, `scoring_version` persisted)
- [x] AFK R5 slice 3 (optional, after slice 2): LLM top-N refinement —
      separate `llm_score`, accompanies composite, never replaces sort default
- [x] AFK R6: LLM remote-status verification per contract — enum +
      restrictions + verbatim evidence + `unknown` fallback, mocked-provider
      contradiction fixtures (before the table so it can show verified status)
- [x] AFK R7 slice 1: results table upgrade — salary/verified-remote/score
      columns, sortable, best-match default order, score breakdown on expand
      (adopt T1's target pattern set if landed)
- [x] AFK R7 slice 2: saveable named search lists — `SearchRun` +
      `SearchRunJob` snapshot rows + dedup rework
      (attach sightings instead of dropping known jobs), multiple lists,
      revisit past searches as historical snapshots
- [x] AFK R7: result curation (P4) — hide/dismiss, min-score /
      verified-remote filters, CSV export of a saved list
- [x] AFK P1: application pipeline UI — status tracking on jobs table using
      existing `JobApplication` model (approved extension R11)
- [ ] AFK P3: scheduled re-search with "N new since last run" diff
      (builds on saved lists above; approved extension R11)
- [ ] AFK P2: per-job tailored resume/cover letter via LLM provider system
      (approved extension R11)

### Thread T3 — Platforms & scraping (HITL-heavy; maintainer-paced)

- [x] AFK R4: platform research doc in `docs/research/` ranking job platforms
      (informs R3 scope and platform priorities)
- [ ] HITL R3: LinkedIn login reliability rework — session-validity probe,
      stateful login UI, visible failure reasons, guided re-login; includes
      pre-search login health probe (P5)
      (needs its own design pass + manual login testing)
- [ ] HITL R3: add next platform per research doc (shared scraper interface)

## Phase 10 — Accounts & Multi-User (end-state; R8–R10)

Groundwork slice lives in Thread T2. The rest is deliberately last (per
maintainer).

- [x] AFK R10: profile visibility status (`draft`/`private`/`public`) + UI
- [x] AFK R9: profiles-per-user UX — present candidates as "my profiles"
      (per-track titles, files, searches scoped per profile)
- [ ] HITL R8: real auth — registration, login, sessions, per-user isolation
      (sweep the retrofit inventory in `docs/design/ownership-groundwork.md`
      onto `get_owned_candidate`)
- [ ] HITL R8: account-type behavior/UI (job-seeking vs job-providing) —
      schema discriminator already lands in T2 groundwork
- [ ] Future R8: employer/recruiter side — search/match public profiles
      (explicitly deferred; keep models compatible)

## Deferred — AI chat/agent track (below product completion)

Resume only when Phase 9 is done or maintainer re-prioritizes. Phase 7 items
overlapping R2 app-wide alignment (sortable tables, theme, layout persistence)
should be folded into Thread T1 slices when those pages are touched, not done
twice.

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
      vision capture, gap audit; inline-JS extraction folded into Thread T1)
