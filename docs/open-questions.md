# Open Questions

Answer inline or delete a question once resolved. Resolved items move to the
bottom section.

## STILL OPEN — answers unblock work

### Q8. Multi-user timing — blocks 9B (and ideally precedes 9D saved lists)

Recommendation: **groundwork-now** — `User` model + `user_id` on `Candidate` +
seeded auto-login dev user (no login UI, no permissions), so later tables are
never migrated twice and testing skips login. Full auth/accounts stay at the
end per maintainer. Alternative: all-at-end, accepting one larger migration.
**Default if unanswered: groundwork-now** (it is invisible and reversible).

### P1–P5. Proposed extensions — approve/reject individually (optional)

Not blocking; on approval they slot per `docs/reviews/roadmap-reorder-2026-07-19.md`:

- **P1 Application pipeline**: UI for the existing unused `JobApplication`
  model (interested → applied → interview → offer/rejected).
- **P2 Per-job tailored documents**: tailored resume/cover letter per job from
  uploaded docs via existing LLM provider system.
- **P3 Scheduled re-search with diff**: re-run a saved search, show "N new".
- **P4 Result curation**: hide/dismiss, min-score / verified-remote filters,
  CSV export.
- **P5 Login health probe**: pre-search session probe, "cookie expired —
  re-login" instead of mid-search failure (joins R3 rework).

### Q7. Legacy root scripts (housekeeping, non-blocking)

`migrate_platform_accounts.py`, `migrate_skills.py`, `copy_candidate_files.py`
at the app root: move to `scripts/`/`history/` or still needed?

### Q6. Provider capability config shape (only when Phase 6 resumes)

Confirm capability config shape before wiring agent-mode fallback. Deferred
with Phase 6; not blocking Phase 9.

## RESOLVED

- **Q1 Which bugs (2026-07-19)**: misimplementations + UI inconsistencies →
  captured as `docs/requirements/product-vision.md`; gap audit ran
  (`docs/reviews/gap-audit-2026-07-19.md`).
- **Q1b scoring / Q1c provenance (2026-07-19)**: approved →
  `docs/design/scoring-and-provenance.md`.
- **Q2 recreate vs enhance (2026-07-19)**: enhance in place — maintainer
  proceeded on this basis all session.
- **Q3 scrapers live? (2026-07-19)**: yes — vision R3 makes login/scraping
  reliability a requirement; stabilize, don't drop.
- **Q4 inline-JS extraction (2026-07-19)**: implicitly approved — folded into
  9A/9C UI-consistency slices (R2 requires it).
- **Q5 remote-rover parity (2026-07-19)**: no longer a driving goal — Phase 7
  demoted to Deferred; overlapping items fold into R2 work.
