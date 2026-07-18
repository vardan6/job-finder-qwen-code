# Design — LLM Remote-Status Verification (R6)

Decided 2026-07-19 per `docs/reviews/plan-review-2026-07-19-product-completion.md`
(finding 7). Implements product-vision R6. Lands in roadmap 9D before the
results-table slice.

## Persisted contract (on `Job`; replaces reliance on bare `ai_remote_score`)

- `verified_remote_status` enum:
  `fully_remote | remote_restricted | hybrid | onsite | unknown`.
- `remote_restrictions` (JSON, only when `remote_restricted`): normalized
  fields — `regions` (e.g. `["US"]`), `citizenship`, `timezone_overlap`,
  `office_visits` (`never | occasional | regular | unknown`). Normalize
  geography to country/region codes, not free text.
- `remote_evidence`: **verbatim quote(s)** from the description (span, not
  paraphrase), required whenever the platform's remote attribute and the text
  disagree; the contradiction is stored as both sides (attribute claim +
  quoted counter-evidence).
- `remote_verified_version`: prompt version. Bumping the prompt version marks
  prior results stale-but-displayed; re-verification is explicit (rerun), never
  automatic recomputation of saved-list snapshots
  (see `docs/design/search-runs-and-lists.md`).

The existing `JobAnalysis` dataclass (`services/job_analysis.py`) already
computes `remote_type`, citizenship, office visits, red flags — this contract
canonicalizes and persists that shape instead of collapsing it to one score.
`ai_remote_score` remains as a derived convenience, not the source of truth.

## Failure and unknown behavior

- Missing/empty description, provider failure, or timeout →
  `verified_remote_status = unknown`, no evidence, no retry loop in the search
  path; unknowns are re-verifiable on demand. Never guess, never default to
  the platform's attribute.

## Test contract (deterministic, no live LLM)

Contradiction fixtures with expected outputs, run against a mocked provider:
- attribute "remote" + "US-only applicants" → `remote_restricted` {regions: US}
  with the quoted restriction;
- "remote" + required timezone overlap → `remote_restricted` (timezone);
- "fully remote" + "quarterly on-site weeks" → `remote_restricted`
  (office_visits: occasional) or `hybrid` per prompt rubric — fixture pins one;
- ambiguous hybrid language ("flexible/hybrid-friendly") → `hybrid`;
- empty description → `unknown`.
Table/filter code is tested against the enum, independent of the LLM.
