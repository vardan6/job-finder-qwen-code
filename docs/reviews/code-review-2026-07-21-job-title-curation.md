# Code review — Job-title parsing and curation

Range reviewed: `6fb7457..working tree` (the title-capture implementation is
already committed; the working tree does not touch this surface). Consulted:
`docs/requirements/product-vision.md`,
`docs/design/scoring-and-provenance.md`, and `roadmap.md`. Reviewer: OpenAI
Codex (same-provider fallback; no independent provider was available).
Date: 2026-07-21.

| # | Finding | Evidence (file:line) | Severity | Risk | Value | Effort |
|---|---------|----------------------|----------|------|-------|--------|
| 1 | The parse-review screen promises that users can remove or correct extracted titles, but saving always appends. A removed title is simply omitted from the request and an edited title with a source document ID is recorded as a different extracted curated value. The old curated title is never removed or updated, so a reload appears to discard the user’s change. | `frontend/templates/candidates/detail.html:1072-1111`; `backend/services/job_title_parser.py:261-282`; `backend/services/provenance.py:5-18` | high | high | high | med |
| 2 | Existing parsed titles report `Saved 0 job titles` when re-saved, because the count measures only new curated rows, not saved extraction facts. This is misleading feedback for an idempotent save and makes a successful persistence action look like failure. | `backend/services/job_title_parser.py:261-285`; `backend/routes/candidate_parser.py:137-140` | med | med | high | low |
| 3 | The title parser prompt asks for every title the candidate is targeting **or has experience with**, with no explicit cap, relevance rubric, or prohibition against seniority fragments/stacked labels. This permits noisy historical-role output such as overly short or compound titles, which then pollutes the preferred-title search profile. | `backend/services/init_prompts.py:11-45`; `backend/database.py:423-445` | high | high | high | low |
| 4 | The dedicated manual-add endpoint always raises on a valid request because `CandidateJobTitle` has no `created_at` mapped attribute. It is separate from parse save but affects the same card’s title lifecycle. | `backend/routes/candidate_parser.py:201-207`; `backend/models/supporting.py:10-29` | med | med | med | low |
| 5 | The title write routes check only that a candidate ID exists, rather than applying the profile-ownership guard used by candidate pages. Once real authentication is enabled, this allows a user who knows an ID to read or modify another user’s titles. | `backend/routes/candidate_parser.py:107-109`, `150-152`, `172-174`, `233-235`; `backend/routes/candidates.py:141-148` | med | high | med | med |

## Details

### 1. Parse review must be a curation operation, not an append operation

The documented contract says the corrected curated set drives search. The
current parse table has remove and text-edit controls, but its POST sends only
the remaining values with `clear_existing: false`. That makes the controls
look effective until reload. Use the curated row identity when a parsed value
matches an existing extraction, and make save replace/synchronise the reviewed
set in one transaction while preserving extraction-occurrence facts for values
that remain. Re-parsing a selected file should replace that file's occurrences,
not indiscriminately delete values contributed by another file.

### 2. Return an outcome that matches user-visible work

The response should distinguish newly created curated titles, updated curated
titles, and already-present titles/occurrences. A title that was successfully
saved idempotently must not render as zero saved.

### 3. Make the extraction prompt target-role oriented

Return a small set of canonical titles (for example three to five), based on
the candidate's stated target roles and strongest, repeated career direction.
Exclude bare seniority words, generic labels, every historical job title, and
slash/parenthetical title concatenations. The model should return an empty list
rather than inventing a target role when the documents do not express one.

