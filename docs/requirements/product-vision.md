# Product Vision — Job Finder (canonical requirements)

Target-state contract, captured 2026-07-19 from maintainer. This is what
"complete" means. Verify implementation against this list; gaps are bugs.
No status here — progress lives in `roadmap.md` / `activeContext.md`.

## Core pipeline (the product in one sentence)

Register a candidate profile → upload files → extract titles/skills per file →
edit/curate them → log in to job platforms → search jobs by profile →
score each job against the profile → verify remote status via LLM →
present results in a best-match-first table.

## R1. Candidate profile

- User registers a candidate profile and uploads **multiple files** into it.
- Each uploaded file gets its **file type classified** (resume / CV / other).
- Per file, **preferred titles and skills are extracted** (LLM-driven). Preferred
  titles are a concise, canonical set of target roles—not every historical
  title—and must not contain generic labels, bare seniority levels, or padded
  near-duplicates.
- Extracted titles/skills are **manually editable** after extraction.
- **Provenance is visible**: UI distinguishes extracted vs user-edited values
  (UX decided in `docs/design/scoring-and-provenance.md`).
- Acceptance: a user can see, per file, what was extracted, correct it, and
  the corrected set is what drives job search. Saving a correction or removal
  must survive reload and must not alter an extraction from an unrelated file.

## R2. UI/UX consistency (app-wide)

- All cards on the candidate profile page (skills, preferred titles, files,
  future cards) share **one consistent card behavior**: same fold/unfold,
  same listing pattern, same file-open affordances, same edit affordances.
- Divergent per-card implementations are defects even when each works alone.
- Beyond the profile page: **the whole app's UI/UX must be cross-compared and
  made consistent** — dashboard, jobs pages, settings, chat all use the same
  patterns for the same interactions (cards, tables, edit modes, modals,
  status badges, loading/error states).

## R3. Platform logins

- Supported now: LinkedIn, Glassdoor. Design must make adding platforms cheap
  (next candidates: We Work Remotely and others from the platform research doc).
- Login must be **reliable and stateful**: clear UI showing logged-in status
  per platform, explicit re-login flow, visible failure reasons.
- Current LinkedIn login is known-unreliable; reliability is a requirement,
  not a nice-to-have.
- **Pre-search login health probe** (approved 2026-07-19): before a search
  runs, each platform session is probed; expired sessions surface
  "cookie expired — re-login" instead of failing mid-search.

## R4. Job search

- Search runs against logged-in platforms using the curated profile
  (titles primarily; skills inform scoring).
- A **research document** (docs/research/) ranks the best job-finding
  platforms to guide which integrations to add next.

## R5. Job scoring

- Every found job is **scored against the candidate profile**.
- Scoring dimensions: title match, skills overlap, optional LLM whole-profile
  pass — approach decided in `docs/design/scoring-and-provenance.md`.
- Score drives default sort order (best match first).

## R6. Remote-status verification

- A job's "remote" attribute is **not trusted**. An LLM pass reads the full
  description/details and returns a verified remote status
  (e.g. `fully_remote` / `remote_restricted (US-only)` / `hybrid` / `onsite`)
  plus the contradicting evidence when the attribute and text disagree.
- Requires a carefully engineered prompt; contradiction cases (attribute says
  remote, text says US-only) are the primary target.

## R7. Results table

- Found jobs render in a **high-quality table**: title, company, salary
  (when available), verified remote status, score, and other key attributes
  as columns.
- Default sort: best match first; columns sortable.
- **Search results are saveable as named lists**: each search can be persisted
  as a list identified by search date plus another distinguishing detail in
  the name (e.g. query/titles used); the user can keep and revisit multiple
  saved lists.
- **Result curation** (approved 2026-07-19): hide/dismiss jobs, min-score and
  verified-remote-only filters, CSV export of a saved list.

## R11. Application tracking & search automation (approved 2026-07-19)

- **Application pipeline**: track per-job status
  (interested → applied → interview → offer / rejected) on the jobs table
  (`JobApplication` model exists; needs real UI).
- **Per-job tailored documents**: generate a tailored resume/cover letter for
  a specific job from the candidate's uploaded docs via the existing LLM
  provider system.
- **Scheduled re-search with diff**: re-run a saved search on demand/schedule
  and show "N new since last run" (builds on saved lists).

## R8. Accounts & multi-user (end-state; captured 2026-07-19)

- The application becomes **multi-user** with real accounts. Timing of the
  switch is a deliberate decision (see open-questions Q8) — end-state yes,
  but groundwork may land earlier to avoid re-migrating data models.
- **Account types**: job-seeking accounts (professionals/employees) now;
  job-providing accounts (recruiters, hiring managers, companies) later —
  current design must not preclude them.
- Job-providing accounts will **search and match public candidate profiles**.
- **Dev/testing convenience**: a seeded, auto-logged-in dev user must exist so
  local testing never starts from a login screen (login bypass or cached
  session in dev mode).

## R9. Multiple profiles per user

- One user owns **multiple candidate profiles**, each targeting a different
  career track (e.g. "AI Engineer" profile vs "Software Developer" profile),
  each with its own titles, skills, files/resumes, and searches.
- Mapping note: today's `Candidate` records already behave like profiles;
  under multi-user each `User` owns N candidate profiles — the existing
  multi-candidate support is the migration path, not a rewrite.

## R10. Profile visibility status

- Each profile has a **visibility status**: `draft` (still working on it) /
  `private` / `public`.
- Only `public` profiles are discoverable by future job-providing accounts.

## Non-goals (current)

- Auto-applying to jobs.
- Employer/recruiter-side features (matching UI, company pages) — future,
  but data model must leave room (account type, profile visibility).

## Quality bar

- UI/UX quality is an explicit requirement ("best UI"), not polish-later:
  profile cards, login flows, and the results table are the three surfaces
  the maintainer flagged as below bar.
