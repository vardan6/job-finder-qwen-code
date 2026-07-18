# Active Context

- Mode: stabilization
- Phase: Phase S — Stabilization (branch `stabilize/cleanup-foundation`)
- State: Full-project review done (2026-07-19): 124/124 tests pass; verdict is enhance-in-place, not recreate. Root handoff/review docs archived to `history/`; maintainer questions captured in `docs/open-questions.md`.
- Next atomic step: R2 pre-review — behavior-level audit of profile-page cards (per-card bugs/divergences) into `docs/reviews/`.
- Next after that: app-wide UI/UX cross-comparison review; maintainer verdicts on open-questions §0 proposed extensions P1–P5.
- Blockers/env: Use `./job-finder-web/venv/bin/pytest -s ...` for focused tests; local `python3` lacks `pytest`.
- Open questions: See `docs/open-questions.md` (7 items, includes carried-over provider capability config shape).
- Discarded as noise: Full rewrite of the app — rejected 2026-07-19, would lose working tested behavior.
