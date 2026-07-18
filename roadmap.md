# Roadmap

## Phase S — Stabilization (active, on `stabilize/cleanup-foundation`)

Decision 2026-07-19: enhance in place, do not recreate — backend is modular
with 124 passing tests. Bug-fix inputs tracked in `docs/open-questions.md`.

- [x] Archive root handoff/review files into `history/`
- [x] Capture maintainer questions in `docs/open-questions.md`
- [x] Collect concrete bug list from maintainer → captured as
      `docs/requirements/product-vision.md` (2026-07-19)
- [ ] Extract inline JS from `chat.html` / `llm.html` / `candidates/detail.html`
      into `frontend/static/js/` modules (pending Q4 approval)

## Phase 9 — Product Completion (requirements: `docs/requirements/product-vision.md`)

Thin vertical slices; each independently verifiable. AFK = can run
autonomously, HITL = needs maintainer decision/review.

- [ ] AFK Gap audit: verify each R1–R7 requirement against implementation;
      write findings table to `docs/reviews/` (drives the rest of this phase)
- [ ] HITL Decide scoring mix (open-questions 1b) and provenance UX (1c)
- [ ] AFK R2: unify profile-page cards into one shared card pattern
      (skills + preferred titles first: same fold/unfold, listing, edit)
- [ ] AFK R1: verify/complete file-type classification (resume/CV/other)
- [ ] AFK R1: provenance — persist extracted-vs-edited per title/skill and
      surface it in the card UI (after 1c decision)
- [ ] HITL R3: LinkedIn login reliability rework — stateful login UI, visible
      failure reasons, re-login flow (needs manual login testing)
- [ ] AFK R5 slice 1: title-match scoring + score column in results
- [ ] AFK R5 slice 2: skills-overlap scoring folded into composite score
- [ ] AFK R6: LLM remote-status verification pass with contradiction evidence
- [ ] AFK R7 slice 1: results table upgrade — key columns, best-match sort
- [ ] AFK R7 slice 2: saveable named search lists (date + distinguishing
      detail), multiple lists, revisit past searches
- [ ] AFK R4: platform research doc in `docs/research/` ranking job platforms
- [ ] HITL R3: add next platform (per research doc, e.g. We Work Remotely)

## Phase 0 — Workflow Bootstrap

- [x] Link shared agent controls, skills, and hooks from `my-workflow`
- [x] Create project-local workflow state files for `/session-open`

## Phase 1 — AI Foundation

- [x] Port the `remote-rover` provider settings backend/UI into `job-finder` as the canonical LLM system
- [x] Port the session-based AI chat shell with persisted sessions, streaming, retry, rename, archive, and provider override
  - [x] Persist chat turns in `AISessionStore` and reconnect `/api/chat` to server-side `session_id`s
  - [x] Load and switch persisted sessions from the chat UI using the new session APIs
  - [x] Add rename, archive, and retry actions to the session-based chat shell
    - [x] Add rename and archive controls to active persisted chat sessions
    - [x] Add per-message retry controls that reuse the selected persisted session
  - [x] Stream assistant responses into persisted sessions instead of waiting for whole replies
    - [x] Add a streaming `/api/chat/stream` backend path that emits assistant chunks and persists the final assistant reply
    - [x] Update the chat UI to consume streamed assistant responses and finalize the active saved session from the terminal event
    - [x] Add focused streaming chat coverage for session events, persisted transcripts, and saved-session reuse
- [x] Add optional candidate attachment and per-session source controls to AI sessions
  - [x] Expose per-session source controls in the chat shell and persist them through the AI session API
- [x] Strip rover-specific modes/tools and define the job-finder routing purposes and capability model
- [x] Implement the initial job-finder tool surfaces for profile, titles, skills, documents, preferences, chat history, settings, and workspace files
- [x] Repoint existing AI-backed features to the new provider/routing system
  - [x] Repoint chat request execution (`/api/chat` + `/api/chat/stream`) to `model_routing.general_chat` with provider/model fallback handling
  - [x] Repoint document-analysis and candidate-analysis entrypoints to the same routing-purpose resolver

## Phase 2 — Agent Expansion

- [x] Expand agent mode beyond the initial toolset
- [x] Add approval-aware mutation flows for non-file writes
- [x] Add job/search-result surfaces and employer-facing context

## Phase 3 — UX Consolidation

- [x] Align the AI chat shell with `remote-rover` UX, including organized session/control layout and Enter-to-send composer behavior

## Phase 4 — Remote-Rover Parity P0 (Core Controls)

- [x] Add ordered fallback routing editor for `fallback_provider_ids` in LLM settings
  - [x] Render per-purpose fallback list in `llm.html` routing editor
  - [x] Support add/remove/reorder of fallback providers
  - [x] Persist and reload ordering through `/api/llm-settings`
- [x] Add provider quick actions in settings table
  - [x] Enable/disable toggle from row action
  - [x] Check health action (provider-level probe)
  - [x] Set as default action for `general_chat`
- [x] Add chat stop-stream control
  - [x] Use `AbortController` in chat request flow
  - [x] Show stop button only during active streaming
- [x] Add archived session management in chat sidebar
  - [x] Active/archived filter toggle
  - [x] Archived-aware list loading/search behavior

## Phase 5 — Remote-Rover Parity P1 (Agent + Routing Intelligence)

- [x] Add per-purpose runtime override toggle (`allow_runtime_override`) in routing UI
- [x] Expand provider templates (Gemini, LM Studio, Mistral, Together, Cohere, HuggingFace)
- [x] Add chat run mode controls (`chat`, `agent`, `intent`, `planning_shell`)
- [x] Add slash-command UX with local fallback commands (`/context`, `/tool-activity`, `/plan`, `/tools`)
- [x] Add agent tool/trace activity rendering in chat messages
- [x] Add context/retrieval diagnostics blocks for assistant responses
- [x] Add in-flight stream recovery across reload/session switch
- [x] Add approval/clarification interaction cards for suspended agent/planning runs

## Phase 6 — Real Agent Runtime

- [ ] Add read-only model-driven agent runtime with typed tools and trace events
  - [x] Add typed read-only tool definitions for `list_data_surfaces` and `candidate_skills_lookup`
  - [ ] Add compact `AIContextService` for agent mode while preserving plain chat behavior
  - [ ] Route `run_mode=agent` through an agent loop for `/api/chat` and `/api/chat/stream`
  - [ ] Enforce explicit provider tool-calling capability/fallback for agent mode

## Phase 7 — Remote-Rover Parity P2 (UX Polish + System Niceties)

- [ ] Add sortable provider registry table (name/type/status/capabilities)
- [ ] Add routing-specific save/reload controls and status feedback
- [ ] Add explicit cancel-edit flow in provider editor
- [ ] Add inline session rename (double-click title in sidebar)
- [ ] Add copy full chat as markdown
- [ ] Persist expanded/collapsed state for trace/diagnostic blocks
- [ ] Add layout persistence (shell/sidebar resizers via `localStorage`)
- [ ] Add JSON settings import/export (providers/routing/AI settings)
- [ ] Add theme controls (light/dark/system) with persistence
- [ ] Add tool discovery surface (`list_data_surfaces`) where domain-appropriate

## Phase 8 — Optional Accessibility Extensions

- [ ] Add TTS support (browser speech and/or local service integration)
