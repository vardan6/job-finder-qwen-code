# Design — LinkedIn Login Reliability Rework (T3 R3)

Scope: `docs/design/platform-adapters.md` already covers the manual sign-in
flow, CAPTCHA handoff, and rate-limit settings. This doc covers what's left
for R3: propagating known-bad session state during a scrape, gating search
on that state, a pre-search health probe (P5), and surfacing failure reasons
where the user is about to search — not just on the accounts page.

## Current state (verified against code)

Already built (`routes/platform_accounts.py`, `browser_manager.py`):
- Account states: `not_connected`, `active`, `login_pending`, `login_failed`,
  `captcha_required`, `expired`, each with a guidance message
  (`_account_guidance`).
- A manual, on-demand live session-validity probe: "Test Connection"
  navigates a real page to the platform and classifies the resulting URL
  (`_session_probe_outcome`) into `active` / `expired` / `captcha_required`.
- A guided re-login flow: Open Browser Login → persistent Chromium profile →
  Finish Browser Login validates auth cookies and saves the session.
- CAPTCHA handoff during a live scrape: `linkedin.py` detects a challenge
  page, hands the page to the manual-login browser, and `job_search.py`
  persists `status="captcha_required"`.

Gaps (from research, file:line references below):
1. **Login-wall detection during a scrape doesn't persist status.**
   `linkedin.py`'s login-wall branch only logs/emits a progress message; it
   never signals `job_search.py` to set `status="expired"`, unlike the
   CAPTCHA path which does. The UI badge stays stale until someone manually
   runs Test Connection.
2. **Search proceeds regardless of known-bad status.** `_search_linkedin`
   (`job_search.py:334-369`) doesn't check `account.status` before scraping
   — it always attempts, even when the account is already `expired` or
   `captcha_required` from a prior run.
3. **No pre-search health probe (P5).** `jobs.py:328-367` and
   `search_config_partial.html` read cached `account.status` at page render;
   the live probe logic (`_session_probe_outcome`) is never invoked from the
   search-config or search-launch path.
4. **Failure reason not visible where the user starts a search.**
   `search_config_partial.html` shows only "Connected/Not Connected" — the
   specific reason (CAPTCHA vs expired vs never logged in) only shows on the
   separate accounts page.
5. **No live/stateful UI.** Status renders once at page load; a status
   change mid-session (e.g. CAPTCHA handoff during a running search) needs a
   manual page refresh to show up.

## Design

### D1 — Persist expired status on login-wall detection (AFK, backend-only)

Mirror the existing CAPTCHA signal. Add a `login_wall_detected` flag to
`LinkedInScraper` (parallel to `manual_challenge_handoff`), set it in the
same place `_is_login_wall` currently only logs. In `job_search.py`, after
`scraper.search_jobs()` returns, check that flag the same way
`manual_challenge_handoff` is checked today, and set
`account.status = "expired"` + commit.

Verifiable without live LinkedIn access: existing scraper tests mock the
page/DOM to trigger `_is_login_wall`; extend that fixture to assert
`account.status == "expired"` after the search-service call, the same
pattern the CAPTCHA fixture presumably already uses.

### D2 — Gate search on known-bad status (AFK, backend-only)

In `_search_linkedin`, before calling `scraper.search_jobs()`, check
`account.status in {"expired", "captcha_required"}`. If so, skip the live
attempt, emit a progress message naming the reason and the fix (reuse the
existing `_account_guidance` strings so there's one source of truth for
copy), and return zero jobs for that platform without spending rate-limit
budget. This is a pure conditional add; no new state, no live probe needed.

### D3 — Surface failure reason in search-config UI (AFK, backend + template)

`jobs.py`'s `platform_status` builder currently returns only a connected
boolean. Extend it to include the account's `status` and its guidance
string (already computed by `_account_guidance` — import and reuse, don't
duplicate). Update `search_config_partial.html` to render the specific
reason instead of a flat "Not Connected", with a link to the accounts page
to act on it. No new live probe call — this reuses D1/D2's now-accurate
persisted status.

### D4 — Pre-search health probe, P5 (implemented; needs manual LinkedIn validation)

Implemented: a "Check LinkedIn connection" button on the search-config page
(`search_config_partial.html`), shown per platform card whenever a LinkedIn
`PlatformAccount` row exists (`platform.account_id` — omitted when the
candidate has never attempted to connect). It calls the existing
`POST /candidates/{candidate_id}/accounts/{account_id}/test` route (no new
backend route needed — that route already runs the same live probe as
"Test Connection" via `_session_probe_outcome`) and updates the status text,
detail line, and platform checkbox in place from the JSON response, without
a full page reload. `jobs.py`'s `platform_status` builder now includes
`account_id` per platform so the template can wire the button.

Covered by fixture tests (`test_linkedin_login_reliability.py`): button
renders with the correct account id when an account row exists, and is
omitted when none exists. These do not exercise the live probe itself
(that's already covered by the existing `/test` route tests) — only that
the search-config page surfaces the control correctly.

Still needs the maintainer to validate against a real LinkedIn session (does
the probe correctly classify a genuinely expired session vs. a CAPTCHA vs. a
healthy one, when triggered from this new search-config entry point) — hence
still HITL, per the roadmap, until that live check is done.

### D5 — Stateful live UI (deferred, not scoped for this pass)

Polling/websocket-driven status updates mid-session are a larger change
(needs a push channel) and aren't blocking the reliability goal — the
existing progress-stream UI already reflects captcha/login-wall events
during a search in real time; what's missing is only the *persisted account
badge* catching up afterward, which D1-D3 fix. Not scoping D5 now; revisit
only if the maintainer reports the stale-badge problem still causing
confusion after D1-D4 land.

## Sequencing

D1 → D2 → D3 are AFK and independently verifiable with existing/extended
mocked fixtures — no live LinkedIn access needed. D4 is the HITL slice: code
is small and builds on D1-D3, but must be validated live by the maintainer
before it's trusted. D5 is deferred.
