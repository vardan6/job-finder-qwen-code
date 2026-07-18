# Roadmap Reorder Review — 2026-07-19

Requested by maintainer: review all plans for ordering problems. Changes
applied to `roadmap.md`; this file records the rationale.

## Ordering problems found → fixes

1. **Saved search lists / provenance before multi-user groundwork.**
   R7b (`SearchRun` model) and R1e (provenance columns) added new schema while
   the Q8 groundwork (`User` + `user_id`) was parked in Phase 10 below them —
   risking double migrations. → New 9B: Q8 decision + groundwork slice land
   before any new-table slice (9C/9D).

2. **Platform research doc scheduled last but consumed earlier.**
   R4 research informs which platforms matter and what the R3 scraper
   interface must support, yet sat after R3 work. → Moved into 9A.

3. **Provenance scheduled before card unification.**
   Provenance badges render inside profile cards; building them on the old
   divergent cards means rework. → 9C order: unify cards → provenance →
   file-type classification.

4. **Remote verification (R6) vs results table (R7 slice 1)** — already
   correct (R6 first so the table shows verified status), kept and made
   explicit; likewise scoring (R5) before best-match sort (R7).

5. **Phase S leftover duplicated future work.** "Extract inline JS from
   chat.html/llm.html/detail.html" overlaps 9C card unification
   (detail.html) and app-wide alignment (chat/llm pages). → Folded into
   9A/9C; Phase S closed.

6. **Deferred chat-parity phases (6–8) sat above the active product work**
   in file order and could be picked up by mistake by `/next-slice`. →
   Moved under an explicit "Deferred" heading with a rule: fold overlapping
   Phase 7 items (sortable tables, theme, layout persistence) into 9A/9C
   slices when those pages are touched.

7. **Completed Phases 0–5 occupied half the file** as narrative history
   duplicated by `progress.md`. → Condensed to one line each.

## Unchanged on purpose

- LinkedIn reliability (9E) stays parallel/late despite being a top
  complaint: it is HITL-heavy (manual login testing) and needs its own
  design pass; it must not block the AFK pipeline work.
- Phase 10 remainder (auth, account types, employer side) stays last —
  explicit maintainer decision.

## Open dependencies

- 9B groundwork is gated on Q8 (open-questions). If Q8 chooses all-at-end,
  9D slice "saved search lists" proceeds anyway and accepts the later
  migration cost.
- Proposed extensions P1–P5 (open-questions §0) are not yet slotted; on
  approval: P5 → joins 9E login rework; P4 → after R7 slice 1; P1–P3 →
  new 9F or Phase 10, maintainer's call.
