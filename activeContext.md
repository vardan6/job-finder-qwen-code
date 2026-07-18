# Active Context

- Mode: stabilization
- Phase: Phase S — Stabilization (branch `stabilize/cleanup-foundation`)
- State: Full-project review done (2026-07-19): 124/124 tests pass; verdict is enhance-in-place, not recreate. Root handoff/review docs archived to `history/`; maintainer questions captured in `docs/open-questions.md`.
- Next atomic step: Get maintainer answers to `docs/open-questions.md` (especially Q1 concrete bug list), then triage into fix slices.
- Next after that: Resume Phase 6 agent runtime (`AIContextService`) once stabilization inputs are settled.
- Blockers/env: Use `./job-finder-web/venv/bin/pytest -s ...` for focused tests; local `python3` lacks `pytest`.
- Open questions: See `docs/open-questions.md` (7 items, includes carried-over provider capability config shape).
- Discarded as noise: Full rewrite of the app — rejected 2026-07-19, would lose working tested behavior.
