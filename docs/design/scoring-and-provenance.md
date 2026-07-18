# Design — Job Scoring & Extraction Provenance

Decided 2026-07-19 (maintainer approved). Implements product-vision R1/R5.
Amended 2026-07-19 per `docs/reviews/plan-review-2026-07-19-product-completion.md`
(findings 1, 3, 4).

## Three-stage job scoring (R5)

1. **Recall**: search platforms by curated preferred titles (cheap, broad).
2. **Score**: every result gets a deterministic composite score.
3. **Refine (optional, bounded)**: LLM whole-profile scoring for the top N
   deterministic results only (default N=20) via routing purpose
   `candidate_analysis`. Never run the LLM stage over the full result set.

### Deterministic score contract

- `title_similarity` — normalized fuzzy match between job title and each
  preferred title (best match wins). Reuse the fuzzy machinery in
  `services/job_deduplication.py` for comparison, but ranking thresholds are
  independent of dedup thresholds — do not share config.
- `skills_overlap` — fraction of profile skills found in the job description:
  - Tokenization: lowercase, strip punctuation; a skill matches on exact token
    sequence OR any alias listed in the skills alias map (config, see below) —
    multiword skills match as phrases, not bags of words.
  - Denominator: count of the candidate's curated skills (not job-side skills).
  - Missing/empty job description → `skills_overlap = null`; composite falls
    back to `title_similarity` alone and the breakdown marks skills as
    "no description".
- Composite = weighted sum, scale **0–100, rounded to nearest integer**
  (start 60/40 title/skills; when `skills_overlap` is null, title weight = 100).
- Weights, N, and the skills alias map live in app config
  (`job-finder-web/backend/config`-adjacent, not hardcoded, not per-request).
- **Version persistence**: every stored score records `scoring_version`
  (algorithm + weights config hash). Scores from older versions are shown as-is
  in saved lists, never silently recomputed (see
  `docs/design/search-runs-and-lists.md`).
- Regression safety: a fixture of representative titles, skill aliases,
  empty/short descriptions with **expected ordering** (not exact numbers)
  guards weight/normalization changes (roadmap R5 slice 1).

### LLM refinement semantics

- The refined result is a **separate field** (`llm_score` + one-line rationale);
  it **accompanies** the deterministic composite — never replaces or adjusts it.
- Default sort precedence: deterministic composite. The UI may offer sorting by
  `llm_score` where present; jobs without it sort by composite.
- `llm_score` records its prompt version; refinement is idempotent per
  (job, profile, prompt version).

UI: table shows the composite score; per-dimension breakdown (and `llm_score`
when present) appears on row expand/hover. Scores must be explainable — never
a bare number.

## Extracted-vs-edited provenance (R1)

R1 acceptance is **per file**: "a user can see, per file, what was extracted."
A single `source_document_id` per curated value cannot represent one value
extracted from two files, so curated values and extraction facts are separate:

- **Curated value** (existing `CandidateJobTitle` / `CandidateSkill` rows):
  what drives search; carries `source: extracted | edited` plus the original
  extracted value when edited. Edits always target the curated value.
- **Extraction occurrence** (new table, many-to-one to the curated value):
  `(document_id, raw_extracted_value, extractor/prompt version, extracted_at)`.
  One row per (document, value) extraction fact; candidate-level dedup of
  curated values no longer discards the second document's association.
  Deleting/reparsing a document touches only its own occurrence rows.
- The per-file inspection view derives from occurrences; the profile cards
  derive from curated values.
- Existing `source_document_id` columns (`models/supporting.py:19,37`) migrate
  into occurrence rows, then are dropped.

UI: subtle badge/dot on `extracted` items; badge changes when edited;
"reset to extracted" restores the original value. Provenance never blocks
editing — it is informational only.
