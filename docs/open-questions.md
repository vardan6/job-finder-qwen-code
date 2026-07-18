# Open Questions

## 0. Proposed extensions — approve/reject individually (2026-07-19)

Suggested by review to complete the vision; not yet requirements:

- **P1 Application pipeline**: `JobApplication` model already exists but has no
  real UI — add status tracking (interested → applied → interview → offer /
  rejected) with a status column/board on the jobs table.
- **P2 Per-job tailored documents**: generate a tailored resume/cover letter
  for a specific job from the candidate's uploaded docs (reuses the existing
  document store + LLM provider system).
- **P3 Scheduled re-search with diff**: re-run a saved search on demand/schedule
  and show "N new since last run" (pairs with R7b saved lists).
- **P4 Result curation**: hide/dismiss jobs, min-score and verified-remote-only
  filters, CSV export of a saved list.
- **P5 Login health probe**: before a search runs, probe each platform session
  and surface "cookie expired — re-login" instead of failing mid-search
  (natural part of the R3 reliability rework).

Questions for the maintainer before/while running the Stabilization phase.
Answer inline or delete a question once resolved.

## 1. Which bugs, concretely? — ANSWERED 2026-07-19

Bugs are misimplementations and UI inconsistencies, not crashes: inconsistent
profile-page cards, missing requested features, unreliable LinkedIn login.
Canonical target behavior now captured in `docs/requirements/product-vision.md`;
the gap audit (roadmap Phase 9 first slice) turns it into a concrete fix list.

## 1b. Scoring approach — DECIDED 2026-07-19

Two-stage scoring approved → canonical in `docs/design/scoring-and-provenance.md`.

## 1c. Extracted-vs-edited provenance UX — DECIDED 2026-07-19

Badge + reset-to-extracted approved → canonical in
`docs/design/scoring-and-provenance.md`.

## Q8. When to do the multi-user switch — needs decision

Maintainer wants multi-user (R8) but at the right time. Recommendation:
**split groundwork from the full switch.**

1. **Now-ish (before model-heavy Phase 9 slices)**: add a `User` model, a
   `user_id` FK on `Candidate`, and a seeded auto-logged-in dev user. Cheap
   while data is small; avoids re-migrating every new table (saved search
   lists, provenance) a second time. No login UI, no permissions — invisible
   groundwork + the dev-user testing convenience.
2. **At the end (per maintainer)**: real auth (registration, login, sessions),
   account types, per-user data isolation, profile visibility enforcement.

Alternative (simplest): defer everything multi-user to the end and accept one
larger migration then. Decide: groundwork-now (recommended) vs all-at-end.

## 2. Recreate vs. enhance — confirmation

My assessment: the backend is in good shape (modular FastAPI app, 124 passing
tests, ADRs, clean docs tree) and a full rewrite would lose working behavior
for little gain. Recommendation is **enhance/stabilize on this branch, not
recreate**. Confirm you accept this, or say if there is a deeper reason to
rebuild (e.g. you want a different stack/architecture).

## 3. Are the scrapers still a live feature?

`backend/scrapers/linkedin.py` and `glassdoor.py` are untested, browser-driven,
and full of broad `except Exception` handlers — the most likely bug nest.
Are LinkedIn/Glassdoor scraping actively used? Options: stabilize with tests,
put behind a feature flag, or drop.

## 4. Frontend refactor appetite

`frontend/templates/chat.html` is ~2,100 lines with large inline scripts
(likewise `settings/llm.html`, `candidates/detail.html`). This is the second
most likely bug source and is untestable as-is. OK to extract inline JS into
`frontend/static/js/` modules as part of stabilization, even though it is a
sizable diff with no visible feature change?

## 5. Remote-rover parity — still a goal?

Phases 4–5 chased `remote-rover` parity and Phase 7 continues it. Is parity
still the target, or has job-finder diverged enough that Phase 7 items should
be re-prioritized on their own merit?

## 6. Provider capability config shape (carried over)

Pre-existing open question from `activeContext.md`: confirm the provider
capability config shape before wiring agent-mode fallback (Phase 6, third
sub-item).

## 7. Root-level legacy scripts

`job-finder-web/migrate_platform_accounts.py`, `migrate_skills.py`, and
`copy_candidate_files.py` sit at the app root. Are these one-time migrations
that can move to `history/` (or a `scripts/` dir), or still needed?
