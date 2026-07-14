# Active Context

- Mode: implementation
- Phase: Phase 6 real agent runtime
- State: Typed read-only agent tool definitions now exist for `list_data_surfaces` and `candidate_skills_lookup`, with schema-validation coverage.
- Next atomic step: Add compact `AIContextService` for agent mode while preserving plain chat behavior.
- Next after that: Route `run_mode=agent` through an agent loop for `/api/chat` and `/api/chat/stream`.
- Blockers/env: Uncommitted worktree is present on `codex/workflow-and-ai-foundation-sync-20260530`; use `./job-finder-web/venv/bin/pytest -s ...` for focused tests because local `python3` lacks `pytest`.
- Open questions: Confirm provider capability config shape before wiring agent-mode fallback.
- Discarded as noise: None.
