# Open Questions

Answer inline or delete a question once resolved. Resolved items move to the
bottom section.

## STILL OPEN

### Q6. Provider capability config shape (deferred with Phase 6)

Confirm capability config shape before wiring agent-mode fallback. Only
relevant when the deferred Phase 6 agent runtime resumes; the implementing
session may propose a shape at that time.

## RESOLVED

- **Q8 multi-user timing (2026-07-19)**: groundwork-now approved — 9B slice:
  `User` model + `user_id` on `Candidate` + seeded auto-login dev user; full
  auth/accounts remain at the end (Phase 10).
- **P1–P5 extensions (2026-07-19)**: all approved → requirements R3 (P5),
  R7 (P4), R11 (P1–P3); roadmap slices 9E (P5), 9D (P4), 9F (P1–P3).
- **Q7 legacy scripts (2026-07-19)**: archived to `history/legacy-scripts/`
  (unreferenced one-time migrations; restructure favors removal).
- **Q1 which bugs (2026-07-19)**: misimplementations + UI inconsistencies →
  `docs/requirements/product-vision.md`; gap audit in
  `docs/reviews/gap-audit-2026-07-19.md`.
- **Q1b scoring / Q1c provenance (2026-07-19)**: approved →
  `docs/design/scoring-and-provenance.md`.
- **Q2 recreate vs enhance (2026-07-19)**: enhance in place on
  `stabilize/cleanup-foundation`.
- **Q3 scrapers live? (2026-07-19)**: yes — R3 makes reliability a
  requirement; stabilize, don't drop.
- **Q4 inline-JS extraction (2026-07-19)**: approved — folded into 9A/9C.
- **Q5 remote-rover parity (2026-07-19)**: no longer a driving goal —
  Phase 7 deferred; overlapping items fold into R2 work.
