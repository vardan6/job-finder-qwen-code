# Plan Review — Product Completion

Scope: `docs/requirements/product-vision.md`,
`docs/design/scoring-and-provenance.md`, `roadmap.md`, `activeContext.md`, and
the plan's assumptions about the current candidate, extraction, job-search,
and routing code. Reviewer: GPT-5 (OpenAI). Date: 2026-07-19.

## Status: RESOLVED — all findings addressed in documentation (2026-07-19)

All 9 findings were triaged (all accepted, none rejected) and fixed at the
planning level the same day. This review is closed; the table below is kept
as the historical record. Where each fix lives:

| # | Resolution |
|---|------------|
| 1 | `docs/design/scoring-and-provenance.md` — curated values split from a new extraction-occurrence table (document, raw value, extractor version, timestamp); per-file view derives from occurrences; `source_document_id` migrates in and is dropped. Roadmap 9C R1 slice reworded to match. |
| 2 | `docs/design/search-runs-and-lists.md` (new) — `SearchRun` + `SearchRunJob` membership/snapshot rows; dedup reworked to attach sightings instead of dropping known jobs; "new since last run" = `first_sighting` rows. Roadmap R7 slice 2 updated. |
| 3 | `docs/design/scoring-and-provenance.md` — LLM refinement is a separate `llm_score` that accompanies (never replaces) the composite; default sort stays deterministic. Roadmap gained explicit optional R5 slice 3. |
| 4 | `docs/design/scoring-and-provenance.md` — renamed three-stage; tokenization, alias map, denominator, null-description fallback, 0–100 integer scale, config home, and `scoring_version` persistence all specified. |
| 5 | `docs/design/ownership-groundwork.md` (new) — `get_current_user()` / `get_owned_candidate()` request-principal contract required for all new Phase 9 code; isolation retrofit inventory recorded for Phase 10. Roadmap 9B expanded. |
| 6 | `docs/design/ownership-groundwork.md` — idempotent dev-user seed, nullable → backfill → NOT NULL sequence, `account_type` discriminator lands in 9B (Phase 10 item narrowed to behavior/UI). |
| 7 | `docs/design/remote-verification.md` (new) — canonical enum, restrictions payload, verbatim-quote evidence, `unknown` fallback, prompt-version persistence, mocked-provider contradiction fixtures. Roadmap R6 slice updated. |
| 8 | Ordering-fixture regression tests added to roadmap R5 slice 1; fixture shape specified in `docs/design/scoring-and-provenance.md`. |
| 9 | `docs/design/search-runs-and-lists.md` — decided: saved lists are historical snapshots (versioned score/status on membership rows); underlying `Job` stays live and deduplicated. |

| # | Finding | Why it matters | Severity | Risk | Value | Effort |
|---|---------|----------------|----------|------|-------|--------|
| 1 | R1 promises titles and skills **per file**, but the provenance design models one `source_document_id` per candidate-level value and the roadmap only adds `source` / original-value fields. Current extraction also deduplicates titles and skills across the whole candidate, so the same value extracted from two files retains at most one file association. | The planned schema cannot show what each file extracted, as R1 acceptance requires, and deleting/reparsing one document can produce incorrect provenance. | high | high | high | med |
| 2 | R7 requires multiple saved lists and R11 requires re-search diffs, but roadmap 9D specifies only a `SearchRun` model. Current deduplication excludes every job already stored for the candidate before saving a run; the plan does not specify a run-to-job association or how an existing job participates in later runs. | A `Job.search_run_id`-style design cannot faithfully represent the same posting in multiple runs/lists, and candidate-wide deduplication would make repeat runs omit known jobs rather than classify them as old versus new. | high | high | high | med |
| 3 | Roadmap R5 slices cover deterministic scoring and the table, but omit the design's optional top-20 LLM whole-profile refinement. The design also does not say whether the refined result replaces, adjusts, or merely accompanies the deterministic composite used for default sorting. | A future agent can legitimately complete every roadmap R5 item while leaving an approved design commitment unimplemented, or can implement incompatible score/sort semantics. | med | med | high | med |
| 4 | The scoring design calls the approach “two-stage” while defining recall, deterministic score, and LLM refine as three stages; it also leaves `skills_overlap` tokenization, denominator, missing-description behavior, score scale/rounding, weight-config home, and algorithm/version persistence unspecified. | Scores will change silently as data or implementation details change, cached/saved results will be hard to reproduce, and exact-match token scoring will mishandle common aliases and multiword skills. | med | med | high | med |
| 5 | The 9B “groundwork-now” slice adds a `User` and `Candidate.user_id`, but the ownership boundary is deferred with real auth to Phase 10. Current routes and AI tools fetch candidates and child records by caller-supplied IDs without an owner predicate, and the plan has no intermediate request-principal contract or inventory for the later isolation retrofit. | Adding ownership data without an access pattern leaves a broad, security-sensitive retrofit across routes, services, AI tools, stored sessions, and file access; new Phase 9 surfaces may repeat the same global-ID assumption. | high | high | high | high |
| 6 | The roadmap says 9B prevents remigrating data models, yet account type is deliberately added later in Phase 10 and no migration/backfill/nullability strategy is recorded for `User`, `Candidate.user_id`, the seeded user, or existing candidates. | The stated sequencing benefit is not guaranteed, and an implementation agent must invent production-safety decisions such as initial nullability, backfill identity, constraints, and dev-seed idempotency. | med | high | high | low |
| 7 | R6 requires a carefully engineered contradiction-evidence pass, but it has no design artifact or acceptance matrix before the single AFK implementation slice. The plan does not define canonical status/evidence storage, geographic-restriction normalization, prompt-version/cache invalidation, or timeout/unknown behavior. | Remote status is a primary correctness target and an LLM output; without a contract, the table/filter behavior and rerun semantics will be brittle and hard to test deterministically. | med | high | high | med |
| 8 | Add a short scoring evaluation fixture before R5 implementation: representative titles, skill aliases, empty/short descriptions, and expected ordering rather than only exact numeric scores. | It would make weight and normalization choices measurable while allowing the algorithm to evolve without accidental ranking regressions. | enhancement | low | high | low |
| 9 | Introduce the run/list aggregate and job association before scoring/remote enrichment, or explicitly persist enrichment snapshots on the association. | This would clarify whether a saved list is a historical snapshot or a live view and prevent later scoring/prompt changes from silently rewriting revisited results. | enhancement | med | high | med |

## Details

### 1. Per-file provenance needs a many-to-many extraction fact

`product-vision.md` R1 says extraction and inspection are per file. In
`models/supporting.py`, both `CandidateJobTitle` and `CandidateSkill` contain a
single nullable `source_document_id`. `document_parser.process_job_titles()`
and the save paths in `job_title_parser.py` / `routes/skills.py` deduplicate by
candidate plus normalized value. The design's proposed `source` and
`original extracted value` fields describe edit history, but do not preserve
the many-to-many fact “document D extracted value V.” Consider separating the
curated candidate value from extraction occurrences (document, raw value,
extractor/prompt version, timestamp), with edits targeting the curated value.

### 2. Saved runs need explicit membership semantics

`JobSearchService._deduplicate_jobs()` compares incoming postings with all
existing jobs for the candidate, and only `unique_jobs` proceed to persistence.
R7 and R11 therefore need more than a run header: for example, stable
candidate-level `Job` identity plus a `SearchRunJob` membership/snapshot row.
The plan should state whether identical postings found by two platforms are
one job with multiple sightings, how reruns attach already-known jobs, and
what timestamp defines “new since last run.”

### 3–4. Define the score contract before slicing it

`scoring-and-provenance.md` says the UI shows “the composite score,” while its
refinement step produces an unnamed LLM score. Specify separate fields and
sort precedence, or a deterministic rule for combining them. Persist an
algorithm/config version with computed scores so saved-list behavior can be
explained after weights change. The existing fuzzy machinery in
`services/job_deduplication.py` may be reusable for title comparison, but its
deduplication thresholds are not automatically suitable ranking semantics.

### 5–6. Make 9B an ownership-boundary slice, not only a schema slice

Examples of current global-ID lookup paths include `routes/preferences.py`,
`routes/documents.py`, `routes/skills.py`, `routes/platform_accounts.py`,
`services/job_search.py`, and `ai_tool_registry._candidate_or_404()`. The plan
should define a request-scoped current user now (the seeded dev user can supply
it), an owner-scoped candidate loader used by all new work, a backfill and
constraint sequence, and a follow-up inventory for existing endpoints. If
account type is certain and cheap, adding its discriminator in 9B better
matches the stated “avoid remigrating” rationale; otherwise narrow that claim.

### 7. Remote verification needs testable outcomes

The current `JobAnalysis` model already has `remote_type`, location,
citizenship, office-visit, and red-flag concepts, but job persistence retains
only `ai_remote_score`. Define the canonical enum and restriction payload,
whether evidence is a quote/span or paraphrase, how conflicts are represented,
and a safe `unknown` result for missing descriptions or provider failure.
Include contradiction fixtures such as “remote” plus US-only, timezone overlap,
occasional office visits, and ambiguous hybrid language.

### 9. Snapshot versus live-list decision

R7 says users revisit saved lists while R5/R6 enrichment may be recomputed.
A historical snapshot preserves what the user saw; a live view reflects new
scores but changes old lists. Recording score/status/prompt versions on run
membership supports both while keeping the underlying job deduplicated.
