# Open Questions

Questions for the maintainer before/while running the Stabilization phase.
Answer inline or delete a question once resolved.

## 1. Which bugs, concretely?

The request said the project "has many, many bugs", but all 124 backend tests
pass and the module structure is sound. The known-bug list is the single most
valuable input for stabilization. Please list concrete symptoms (page, action,
expected vs actual), even roughly — e.g. "chat stream hangs after stop",
"skills modal loses edits". Without this, stabilization has to guess where the
pain is (my guess: frontend templates and scrapers, since those have no test
coverage).

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
