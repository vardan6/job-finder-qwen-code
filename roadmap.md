# Roadmap

## Phase 0 — Workflow Bootstrap

- [x] Link shared agent controls, skills, and hooks from `my-workflow`
- [x] Create project-local workflow state files for `/session-open`

## Phase 1 — AI Foundation

- [ ] Port the `remote-rover` provider settings backend/UI into `job-finder` as the canonical LLM system
- [ ] Port the session-based AI chat shell with persisted sessions, streaming, retry, rename, archive, and provider override
- [ ] Add optional candidate attachment and per-session source controls to AI sessions
- [ ] Strip rover-specific modes/tools and define the job-finder routing purposes and capability model
- [ ] Implement the initial job-finder tool surfaces for profile, titles, skills, documents, preferences, chat history, settings, and workspace files
- [ ] Repoint existing AI-backed features to the new provider/routing system

## Phase 2 — Agent Expansion

- [ ] Expand agent mode beyond the initial toolset
- [ ] Add approval-aware mutation flows for non-file writes
- [ ] Add job/search-result surfaces and employer-facing context
