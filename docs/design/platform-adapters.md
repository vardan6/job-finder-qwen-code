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
