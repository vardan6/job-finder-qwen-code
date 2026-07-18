# Active Context

- Mode: implementation (Phase 9 product completion)
- Phase: 9A — reviews first, branch `stabilize/cleanup-foundation`
- State: All planning captured and committed through 08d7700 — vision R1–R10, scoring/provenance design, gap audit, roadmap reordered into execution order (9A→9E, rationale in `docs/reviews/roadmap-reorder-2026-07-19.md`).
- Next atomic step: 9A slice 1 — behavior-level audit of profile-page cards into `docs/reviews/` (per-card bugs/divergences in fold/unfold, file open, listing, edit flows).
- Next after that: 9A app-wide UI/UX cross-comparison; then 9B needs HITL Q8 verdict before any new-table slice.
- Blockers/env: HITL pending — Q8 multi-user timing + P1–P5 extension approvals in `docs/open-questions.md`. Use `./job-finder-web/venv/bin/pytest -s ...`; local `python3` lacks `pytest`.
- Open questions: `docs/open-questions.md` — Q8 (groundwork-now recommended), §0 P1–P5, Q3 scraper fate, Q4 inline-JS approval (now folded into 9A/9C), Q5 parity relevance, Q7 legacy scripts.
- Discarded as noise: Full rewrite (rejected — 124/124 tests pass); doing provenance before card unification (rework); scheduling new tables before Q8 groundwork (double migration).
