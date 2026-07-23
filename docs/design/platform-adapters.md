# Design — Job Platform Adapters

Each job platform exposes one small adapter boundary rather than platform
markup or session assumptions leaking into search orchestration.

## Contract

`backend.scrapers.base.PlatformJob` is the normalized, source-preserving
result returned by an adapter. It carries the job identity, source and apply
URLs, title/company/location, optional description, remote eligibility, and
source timestamp. `JobPlatformAdapter.search_jobs()` is the common async
search surface.

`JobSearchService` selects the adapter, records its result count, and applies
the candidate-level deduplication/search-run logic. Adapters must not create
or mutate `Job`, `SearchRun`, or `SearchRunJob` records directly.

Adapters report session outcome (rate-limited, login wall, CAPTCHA handoff,
last error) through `scrapers.base.ScraperSessionState` attributes instead of
raising, since a blocked search still returns a result rather than an
exception. `JobSearchService._apply_scraper_outcome` is the one place that
turns those attributes into skip/error reasons and `PlatformAccount.status`
updates, applied uniformly to every platform.

## Shared browser session lifecycle

Browser-driven adapters (LinkedIn, Glassdoor) subclass
`scrapers.playwright_base.PlaywrightJobScraper`, which owns the whole session
skeleton once: acquiring the global search lock, gating on rate limits,
launching the browser, navigating, dispatching login-wall/CAPTCHA detection,
the collect/scroll loop, cookie persistence, success logging, and uniform
error capture into `ScraperSessionState`. `_run_search_session` is that
skeleton.

A concrete adapter keeps its own thin `search_jobs` (so platform-specific
parameters stay explicit at the call site) and declares only what differs:
search URL, per-card extraction, and CAPTCHA policy (`_on_captcha` — cooldown
for Glassdoor, manual handoff for LinkedIn). Login-wall/CAPTCHA detection and
the description-panel fetch are declared as data, not overridden methods: each
adapter sets the URL tokens, credential-field selectors, results-present
selector, and CAPTCHA-widget selector as class attributes, and the base
evaluates them with fixed precedence (a challenge URL blocks outright;
otherwise rendered results mean the page is fine and only a present widget
counts). This keeps a platform's block signatures readable in one place and
makes detection testable through a fake page exposing only `url` and
`query_selector` (`tests/test_scraper_block_detection.py`).

Because the skeleton is provider-neutral it is unit-tested through fake
page/manager objects (`tests/test_playwright_scraper_base.py`) without a live
browser. Fixture-only adapters like We Work Remotely do not use this base and
stay import-light.

## Policy and live access

An adapter may parse saved fixtures without provider access. Any live browser,
network, login, or session operation must first pass the provider-policy and
session-health workflow. Until that is authorized and manually validated, the
adapter must fail closed with a visible result rather than attempting access.

We Work Remotely is the reference implementation: it is selectable in search
configuration but its live navigation remains intentionally unavailable until
the R3 HITL validation is complete.

## Manual browser sign-in

Manual sign-in uses a persistent Chromium profile per candidate and platform.
The Finish Browser Login action reads that profile, encrypts its storage state
into the account session, and then closes the manual browser context. This
separates manual login state from scraper contexts and allows Finish to recover
after an application reload. Logging out removes both the encrypted saved
session and that temporary profile.

If LinkedIn presents a CAPTCHA during a search, the scraper transfers the
current authenticated cookie state into that persistent manual profile and
leaves its visible CAPTCHA page open. It releases the search without trying to
solve the challenge; the account becomes `captcha_required`. The user completes
the challenge directly in that browser and uses Finish Browser Login to save
the refreshed session.

## LinkedIn rate-limit settings

LinkedIn request counters and cooldowns are scoped to one candidate's saved
LinkedIn account (`linkedin:<candidate_id>`), not shared across every account.
The account card owns the editable policy: hourly and daily request limits,
request delay range, and operating-hours window. Defaults remain conservative.

For every editable numeric limit, `0` disables that restriction: an hourly or
daily limit of zero is unlimited; a zero minimum delay removes request delay;
and a zero start or end hour disables the operating-hours window. The user can
reset only that account's counters and cooldown. This is an explicit testing
and account-owner control, so the UI must warn that relaxed limits increase
provider restriction risk.
