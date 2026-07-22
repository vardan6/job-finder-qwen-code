# Design — 9B Ownership Groundwork (User model + access pattern)

Decided 2026-07-19 per `docs/reviews/plan-review-2026-07-19-product-completion.md`
(findings 5, 6). Implements the approved Q8 groundwork-now decision for
product-vision R8. Real auth stays in Phase 12; this slice makes 9B an
**ownership-boundary slice, not only a schema slice**.

## Schema

- `User`: id, email, display name, `account_type` (string discriminator,
  default `job_seeking`; `job_providing` reserved — schema now because it is
  certain per R8 and cheap, behavior/UI stays Phase 12), created_at.
- `Candidate.user_id` → FK to `users`.

## Migration / backfill sequence (single slice, in order)

1. Create `users`; seed the dev user **idempotently** (get-or-create by fixed
   email `dev@local`) — safe to rerun, never duplicates.
2. Add `candidate.user_id` **nullable**.
3. Backfill: all existing candidates → seeded dev user.
4. Tighten to `NOT NULL` (SQLite: enforce in model + creation paths; table
   rebuild only if cheap).

## Request-principal contract (the part that prevents the retrofit)

- `get_current_user()` FastAPI dependency. Phase 9: returns the seeded dev
  user (auto-login, no login UI). Phase 12: replaced by real session auth —
  call sites do not change.
- `get_owned_candidate(db, user, candidate_id)` — the **only** approved way to
  load a candidate: filters by `user_id`, 404 on miss or foreign owner.
- **All new Phase 9 code** (scoring, search runs, remote verification, new
  routes/AI tools) must use these two; direct
  `db.query(Candidate).get(candidate_id)`-style global lookups in new code are
  defects. AI tools receive the principal from the chat session context.

## Isolation retrofit inventory (Phase 12, R8 real-auth slice)

Existing global-ID lookup paths to sweep onto `get_owned_candidate` when real
auth lands — inventory, not current defects:
`routes/preferences.py`, `routes/documents.py`, `routes/skills.py`,
`routes/platform_accounts.py`, `services/job_search.py`,
`ai_tool_registry._candidate_or_404()`, stored chat sessions, uploaded-file
access paths. Grep check: `_candidate_or_404|query(Candidate)`.
