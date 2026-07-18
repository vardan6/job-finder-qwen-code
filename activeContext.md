# Active Context

- Mode: implementation (Phase 9 product completion)
- Phase: 9A — reviews first, branch `stabilize/cleanup-foundation`
- State: All planning captured and committed through 08d7700 — vision R1–R10, scoring/provenance design, gap audit, roadmap reordered into execution order (9A→9E, rationale in `docs/reviews/roadmap-reorder-2026-07-19.md`).
- Next atomic step: 9A slice 1 — behavior-level audit of profile-page cards into `docs/reviews/` (per-card bugs/divergences in fold/unfold, file open, listing, edit flows).
- Next after that: 9A app-wide UI/UX cross-comparison; then 9B needs HITL Q8 verdict before any new-table slice.
- Blockers/env: None — Q8 and P1–P5 resolved 2026-07-19; 9B groundwork approved. Use `./job-finder-web/venv/bin/pytest -s ...`; local `python3` lacks `pytest`.
- Open questions: only Q6 (provider capability shape, deferred with Phase 6) — see `docs/open-questions.md`.
- Discarded as noise: Full rewrite (rejected — 124/124 tests pass); doing provenance before card unification (rework); scheduling new tables before Q8 groundwork (double migration).
