# Design — Job Scoring & Extraction Provenance

Decided 2026-07-19 (maintainer approved). Implements product-vision R1/R5.

## Two-stage job scoring (R5)

1. **Recall**: search platforms by curated preferred titles (cheap, broad).
2. **Score**: every result gets a deterministic composite score:
   - `title_similarity` — normalized fuzzy match between job title and each
     preferred title (best match wins).
   - `skills_overlap` — fraction of profile skills found in the job
     description (normalized token match).
   - Composite = weighted sum (start 60/40 title/skills; weights in config,
     not hardcoded).
3. **Refine (optional, bounded)**: LLM whole-profile scoring for the top N
   results only (default N=20) via routing purpose `candidate_analysis`.
   Never run the LLM stage over the full result set.

UI: table shows the composite score; per-dimension breakdown appears on
row expand/hover. Scores must be explainable — never a bare number.

## Extracted-vs-edited provenance (R1)

- Each extracted title/skill row stores `source: extracted | edited`
  plus the original extracted value when edited.
- UI: subtle badge/dot on `extracted` items; badge changes when edited;
  "reset to extracted" affordance restores the original.
- Provenance never blocks editing — it is informational only.
