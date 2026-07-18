# Design — Search Runs, Saved Lists, and Job Membership

Decided 2026-07-19 per `docs/reviews/plan-review-2026-07-19-product-completion.md`
(findings 2, 9). Implements product-vision R7 (saved lists) and R11 (re-search
diff). Lands in roadmap 9D after 9B groundwork.

## Problem

`JobSearchService._deduplicate_jobs()` (`services/job_search.py`) drops any
incoming posting that matches an existing job for the candidate. A bare
`SearchRun` header on `Job` therefore cannot represent the same posting in two
runs, and reruns would omit known jobs instead of classifying them old vs new.

## Model

- **`Job` stays candidate-level and deduplicated** — one row per real-world
  posting per candidate. Identical postings found by two platforms are one
  `Job` with multiple sightings.
- **`SearchRun`** — run header: candidate, name (search date + distinguishing
  detail per R7), query/titles used, platform set, started/finished timestamps.
- **`SearchRunJob`** — membership + snapshot row, one per (run, job):
  - `first_sighting: bool` — true when this run created the `Job` row.
    "N new since last run" = count of `first_sighting` rows in the run.
  - Snapshot fields captured at run time: composite score + `scoring_version`,
    `llm_score` + prompt version (if run), verified remote status + its prompt
    version, salary as seen.
  - Which platform(s) sighted it in this run.

## Dedup rework (replaces silent dropping)

On each incoming posting: match against existing candidate jobs (existing
fuzzy machinery). Match → attach a `SearchRunJob` to the existing `Job`
(`first_sighting = false`), optionally refresh volatile job fields. No match →
create `Job` + `SearchRunJob` (`first_sighting = true`). Nothing is dropped;
"already known" becomes membership data instead of an exclusion.

## Snapshot vs live (decided: snapshot)

A saved list is a **historical snapshot**: revisiting it renders the
`SearchRunJob` snapshot fields, so later scoring/prompt changes never rewrite
what the user saw. The `Job` row itself stays live (current status, application
tracking). UI may indicate "score recomputed since this run" by comparing
snapshot `scoring_version` to current, but never overwrites the snapshot.

## Sequencing

`SearchRun`/`SearchRunJob` are new tables → they land after 9B groundwork
(user_id exists first, nothing migrated twice). The dedup rework ships in the
same slice as `SearchRunJob` (R7 slice 2) — earlier slices (scoring, remote
verification) write to `Job` and are snapshotted retroactively only from the
first run after this slice.
