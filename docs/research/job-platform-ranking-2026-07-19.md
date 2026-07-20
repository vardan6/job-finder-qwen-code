# Job-platform ranking for R3/R4

**Research date:** 2026-07-19  
**Decision supported:** the next platform after LinkedIn, and the order in
which R3 platform work should be scoped.

## Recommendation

Implement **We Work Remotely (WWR)** next, after the LinkedIn reliability
rework. It is purpose-built for remote jobs, exposes programming and DevOps
categories, and tells applicants whether a posting is available worldwide or
in a particular region. That directly supports the candidate's remote-from-
Armenia search across US, EU, and Canada employers.

The R3 implementation should provide a stateful platform integration: show
WWR login/session health, search only after a successful health check, and
hand off applications to the employer's ATS, site, or email flow.

**Next in line:** Remote OK, but only after WWR. Its JSON feed makes it a
candidate for a future feed adapter. Its current feed contains noisy and
inconsistently structured listings, so it needs stronger validation and
deduplication before it can outrank WWR for this candidate.

## Evaluation criteria

Scores are 1 (poor) to 5 (strong). The weighted score is a prioritization aid,
not a claim of job-market coverage.

| Criterion | Weight | What earns a high score |
|---|---:|---|
| Remote and regional fit | 30% | Explicit remote work plus a way to determine Armenia/US/EU/Canada eligibility |
| Target-role fit | 25% | Software test, test infrastructure, developer tools, or engineering inventory |
| Result/action quality | 15% | Fresh postings, useful metadata, and clear application destination |
| Integration viability | 20% | Stable account/session or feed integration path |
| Account friction | 10% | Low login friction and clear application handoff |

## Ranked platform candidates

| Rank | Platform | Remote / role fit | Integration and login characteristics | Weighted score | Decision |
|---:|---|---|---|---:|---|
| 1 | **We Work Remotely** | Remote-only board; programming, software-development, and DevOps categories; regional tags distinguish `Anywhere in the World` from restricted roles. | Account/session flow and external employer application handoff. | **4.05** | **Implement next after LinkedIn** |
| 2 | **Remote OK** | Remote-first, including engineering listings; its JSON endpoint exposes title, company, tags, location, application URL, and date. | Public JSON feed and external application handoff. | **3.75** | Research/design after WWR; candidate for the first feed adapter |
| 3 | **Wellfound** | Strong startup/technology inventory, remote filters, and per-posting "Hires Remotely From" eligibility can prevent false remote matches. | Candidate account/profile and location-aware search. | **3.60** | Defer integration |
| 4 | **Glassdoor** | Valuable supplementary jobs and company/salary research; already in the product's declared supported set. | Existing account/session integration. | **3.05** | Stabilize later; do not make the next new adapter |
| 5 | **Indeed** | Broad volume can surface relevant roles, but is less targeted to remote international eligibility. | Broad volume with variable account requirements. | **2.45** | Defer integration |

### Why WWR wins despite the login requirement

WWR's login requirement increases R3's session-management work, but its core
inventory matches the product's remote-first goal more closely than the broad
aggregators. The platform provides role categories relevant to the candidate,
states that applications route to the employer's own process, and explicitly
advises applicants outside the US to use regional tags. This makes the
eligibility field and external `apply_url`/handoff central parts of the shared
platform contract.

Remote OK is deliberately second: the documented feed lowers technical
friction, but the observed payload includes incomplete titles, broad tags, and
some off-target listings. It should be filtered by curated titles/skills,
remote-location eligibility, and existing cross-platform deduplication before
results are shown as high-confidence matches.

## R3 scope and implementation priorities

1. Finish LinkedIn's session-validity probe, clear failure reasons, and guided
   re-login. It establishes the shared login-health contract.
2. Add WWR using that contract: account/session status, visible re-login,
   search by curated titles, record the regional eligibility tag verbatim, and
   open the employer application flow rather than submitting applications.
3. Keep the adapter boundary small and provider-neutral: result identity,
   title, company, description, posted time, source URL, apply URL, remote
   eligibility, source timestamp, and provenance. Do not bake a WWR-specific
   login or markup assumption into shared search logic.
4. Evaluate Remote OK next as a feed adapter; require a
   small sampled quality review (target-title precision, duplicate rate,
   Armenia eligibility coverage, and stale/invalid application links) before
   promoting it to the default search set.

## Integration/login summary

| Platform | Login needed for core job-seeker flow | Integration focus | Application posture |
|---|---|---|---|
| WWR | Yes. | Stateful account/session health. | Redirect, employer ATS, or email. |
| Remote OK | Not required for the public feed; subscription/login offers extra platform features. | Feed quality, validation, and deduplication. | External job/application URL. |
| Wellfound | Yes, account/profile. | Location-aware search. | One-click applications/profile flow. |
| Glassdoor | Treat as stateful for product consistency. | Session reliability. | Platform/external flow. |
| Indeed | Varies by feature. | Broad-search relevance. | Platform/external flow. |

## Sources and verification

All sources below were checked on 2026-07-19.

- [We Work Remotely FAQ](https://weworkremotely.com/frequently-asked-questions) — account requirement, role categories, regional tags, and external application methods.
- [Remote OK jobs](https://remoteok.com/jobs) and [Remote OK JSON API](https://remoteok.com/api) — the site links its API/JSON feed; the sampled payload exposes source fields used in the assessment.
- [Wellfound remote-job search guidance](https://help.wellfound.com/article/762-remote-job-search-filters) — remote filters and per-posting hiring-location eligibility.
