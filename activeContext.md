# Active Context

- Mode: implementation
- Phase: Phase 1 — AI Foundation
- State: Shared workflow assets are linked; ADR 0001 and the AI migration design doc capture the chosen source-of-truth direction for replacing the legacy `job-finder` LLM setup.
- Current task: Port the `remote-rover` provider settings backend/UI into `job-finder` as the canonical LLM system.
- Next atomic step: Inspect `remote-rover/gcs_server` provider settings backend and map the minimal transplant plan into `job-finder-web`.
- Next after that: Port the session-based AI chat shell with persisted sessions and remove rover-specific surfaces.
- Blockers/env: Shared skills and Codex hook wiring are symlinked from `/mnt/c/Users/vardana/Documents/Proj/my-workflow`; session state files now exist locally in this repo; migration decisions are captured in `docs/adr/0001-ai-foundation-source-of-truth.md` and `docs/design/ai-foundation-migration.md`.
- Open questions: Exact module boundaries for copied provider/session/tool runtime code inside `job-finder-web` are still open and should be chosen during the first transplant slice.
- Discarded as noise: Do not introduce a separate “workspace” object for candidate context; AI session remains the primary unit.
