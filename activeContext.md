# Active Context

- Mode: implementation (Phase 9 product completion)
- Phase: 9A — reviews first, branch `stabilize/cleanup-foundation`
- State: Planning fully closed through 09309ec; plan-review findings (2026-07-19) applied to docs — design contracts now in `scoring-and-provenance.md`, `search-runs-and-lists.md`, `ownership-groundwork.md`, `remote-verification.md`; roadmap 9B/9C/9D/10 slices updated to match. Zero open questions.
- Next atomic step: 9A slice 1 — behavior-level audit of profile-page cards into `docs/reviews/` (per-card bugs/divergences in fold/unfold, file open, listing, edit flows).
- Next after that: 9A app-wide UI/UX cross-comparison; then 9B groundwork slice (approved) before any new-table slice.
- Blockers/env: None — Q8 and P1–P5 resolved 2026-07-19; 9B groundwork approved. Use `./job-finder-web/venv/bin/pytest -s ...`; local `python3` lacks `pytest`.
- Open questions: none — all resolved 2026-07-19 (`docs/open-questions.md`).
- Discarded as noise: Full rewrite (rejected — 124/124 tests pass); doing provenance before card unification (rework); scheduling new tables before Q8 groundwork (double migration).
