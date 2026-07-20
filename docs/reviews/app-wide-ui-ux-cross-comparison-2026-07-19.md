# App-wide UI/UX cross-comparison — 2026-07-19

Scope: rendered web templates, shared CSS/JS, and their visible interaction
states. This is the T1 R2 inventory that complements the profile-card behavior
audit; it establishes the target pattern set for subsequent UI work. It does
not change product behavior or make a design decision already reserved for
another roadmap slice (notably scoring, remote verification, or provenance).

## Inventory

| Pattern | Where it is consistent | Divergence / evidence | Target decision |
| --- | --- | --- | --- |
| Page header and primary action | `jobs/search.html` uses `page-header` + `page-header-actions`; lists consistently put the primary action at page top. | Candidate, job, account, preference, and settings pages each hand-roll a Bootstrap row or `d-flex` header (`candidates/list.html`, `jobs/list.html`, `accounts/list.html`, `preferences/edit.html`, `settings/functions.html`). Alignment and wrapping consequently differ, especially at smaller widths. | Adopt one page-header layout: title, optional concise description, and a wrapping action group. Use it for all full pages; retain the chat shell as its specialized workspace layout. |
| Cards and section headers | Shared `.card`, `.section-card`, and `.section-list` styles provide a coherent surface (`static/css/style.css`). Dashboard, job detail, and settings use basic section cards. | Headers range from plain, tinted Bootstrap utility headers, `shadow-sm border-0` local overrides, to gradient cards; profile cards add bespoke collapses. Account and preference headers use `bg-* text-white`, but the global CSS deliberately makes those headers dark text, producing a conflicting class contract. | Define named variants only: **section** (default header), **summary/metric** (clickable metric card), **status/help** (semantic tint), and **action/CTA**. All collection/detail cards use `section`; a header contains title, optional count/status, and actions. |
| Fold/unfold | Function mappings uses Bootstrap accordion; several profile cards fold. | Most cards never fold, while profile cards mix click targets and static headers; Skills is always open. The profile audit records the per-card behavior and required normalization. | Folding is opt-in for dense, independent profile collections. Use one accessible header button with `aria-expanded`, a visible chevron, and no toggle on header actions. Do not add collapse controls to ordinary page sections merely for uniformity. |
| Tables and row actions | Candidate and job list tables share `table table-hover`; CSS gives them common padding and hover behavior. | Candidates render a bare responsive table; jobs wrap it in a card. Candidate actions have visible text and native `confirm`; job actions are icon-only and HTMX uses a different confirmation mechanism. Neither table has an explicit caption, loading state, or an in-table retry/error treatment. | Collection tables live in a section card with responsive overflow, a concise count, consistent action column, and an explicit empty state. Use labelled icon+text actions until responsive design supplies an overflow menu. Destructive actions use one confirmation and one post-action feedback mechanism. T2's results-table slice should use this pattern. |
| Edit/save/cancel | Candidate and preference forms offer primary save + secondary cancel. LLM settings supplies in-page success/error alerts. | Job status is HTMX-submitted with no visible pending/result state; function mapping auto-saves field-by-field; profile titles use inline draft state and browser alerts; Skills uses a modal manager. Candidate edit incorrectly promises immediate save although it requires submission. | Every edit surface declares its save model: form submit, explicit inline save, or auto-save. For async work: disable/mark pending, retain a draft on failure, and show an in-context result. Each explicit edit surface provides Cancel/revert. Correct the candidate copy in the card-unification slice. |
| Modals | File selector and skills manager use Bootstrap modal structure, labelled titles, close controls, footer cancel, loading spinner, and inline panel states. | `detail.html`'s document-view modal lacks a usable PDF open/download action (profile audit); title parsing uses a separate modal then an in-page review, while Skills uses one manager modal. Some failure paths use `alert()` instead of modal-local feedback. | Use modals for short, reversible focused work only. Modal contract: labelled title, close/cancel, loading, empty, error, and success/result state inside the modal; no browser alerts. Curated title and skill parse/edit flows become one interaction family in the shared-card slice. |
| Badges and status vocabulary | Job platform/status and LLM provider health map semantic states to Bootstrap badges; account status badges are readable and icon-supported. | The same colors mean unrelated things: `bg-info` is a profile document type, a slider value, a job status, and AI/extraction; `bg-primary` is both LinkedIn and active job status. Some modern `text-bg-*` and older `bg-*` conventions mix (`settings/llm.html` versus other pages). “AI” is used as a source badge where R1 needs extracted/edited provenance. | Use semantic status tokens: neutral, info, success, warning, danger; reserve brand/platform badges for identity. Status badges require text, not color alone. Do not introduce provenance badges before T1 R1's designed occurrence model; that slice defines extracted/edited/reset labels. |
| Loading, error, and success feedback | File selector, Skills modal, document upload, search-result partial, LLM settings, and chat all render some inline loading/error/success feedback. | Most CRUD pages rely on query-string flash messages, browser `alert()`, or a console-only error. Global HTMX errors invoke `alert()` (`static/js/app.js`); auto-dismiss timing can remove a message before it is read. Empty/error semantics vary between alerts, table rows, and plain text. | Establish reusable inline feedback regions: request-pending spinner/disabled control; success alert that remains until dismissed or navigation; error alert with retry where feasible; empty state with explanation and primary action. Replace browser alerts progressively as each surface is touched; a global HTMX handler should target the originating region. |
| Empty states | Candidate and job lists provide actionable info alerts; chat has a dedicated empty workspace. | LLM provider empty state is a table row; function mappings uses a list row; Skills says “No skills added yet” inside a modal; dashboard renders zero-value cards without an onboarding action. | Empty collections use a compact empty-state component within their owning card/table: icon, what is absent, why it matters if useful, and one primary next action. Keep chat's richer empty state as its workspace-specific variant. |
| Confirmation and destructive actions | Candidate delete uses a native confirmation; jobs use `hx-confirm`; accounts use inline `onclick=confirm`; title editing has its own empty-list confirmation. | Wording and triggering mechanism differ; post-delete feedback is not predictable. Some destructive routes are represented only with icons. | One confirmation convention with object-specific, consequence-first wording, Cancel as the safe default, and success/error feedback after completion. Apply it when each owning page is changed rather than as a broad rewrite. |
| Navigation and context | Base navigation gives a clear active state for top-level pages; full-page detail/edit forms usually offer a Back/Cancel route. | Dashboard candidate link omits the canonical trailing slash; job detail has three unwrapped header actions; Settings index uses a separate back button. The candidate profile repeats job-search entry points (profile audit). | Use the page-header action group for contextual navigation. One primary action per page; secondary/contextual actions follow it. Remove or contextualize duplicated profile search entry points during profile-card work. |

## Target pattern set

The following is the implementation contract for R2 work. It intentionally
uses existing Bootstrap and project CSS primitives first; extraction into
templates/macros should follow only when a slice changes at least two callers.

| Pattern | Required structure and behavior |
| --- | --- |
| **Page header** | `page-header` with title/optional description and `page-header-actions`. One primary action; secondary/back actions in the same wrapping group. |
| **Section card** | `.card.section-card`, header with title/icon, optional count or semantic status, and actions; body owns content and feedback. Default section headers are not colored. Help/status/CTA variants are explicit exceptions. |
| **Collection** | Filter active data before count/slice; show accurate count; responsive table or list; action column/actions have visible labels; empty state stays inside the owner; continuation is reversible (“Show N more” / “Show less”). |
| **Profile collection card** | The section-card contract plus optional accessible fold control. Its header action never toggles; Titles and Skills use the same parse/edit/list lifecycle. The detailed per-card rules remain in `profile-page-card-audit-2026-07-19.md`. |
| **Form/edit state** | Explicit save model, primary Save, secondary Cancel, validation near the field, pending state on async submission, and durable in-context success/error feedback. |
| **Modal** | Accessible title and close, focused purpose, internal pending/empty/error/result regions, and footer Cancel plus primary action. Never use browser `alert()` as the modal outcome. |
| **Feedback** | Semantic alert regions for success, warning, error, and pending; errors explain the failed operation and offer retry when possible. The originating component owns feedback, with a page-level fallback. |
| **Status badge** | Text + optional icon; semantic color for state and a distinct identity treatment for platforms. Use one `text-bg-*`/project-token convention in touched templates. |

## Prioritized follow-up

1. **P0 — make the target pattern real in the already-planned profile-card
   unification slice.** Fix the documented Skills fold violation, truthful
   active collection counts, reversible continuations, consistent row actions,
   and profile edit/parse affordances. Do not pre-empt R1 provenance.
2. **P1 — have T2 R7 results-table work adopt the collection/table contract.**
   It is the next large table touchpoint and should not introduce a third row-
   action, sort, empty, or feedback convention.
3. **P1 — normalize asynchronous feedback as surfaces are touched.** Begin
   with profile modals and HTMX job actions; preserve chat's specialized
   streaming feedback rather than forcing it into a generic card pattern.
4. **P2 — migrate legacy card/header variants opportunistically.** Dashboard,
   accounts, preferences, and settings can converge when a feature change
   reaches them; this review does not justify a standalone cosmetic rewrite.

## Verification performed

- Inspected every top-level page family and shared template component under
  `frontend/templates/`, plus `base.html`, `static/css/style.css`, and
  `static/js/app.js`.
- Cross-checked the profile-specific conclusions against the existing
  `profile-page-card-audit-2026-07-19.md` and roadmap ordering.
- No runtime data, source code, or state files were changed. This document is
  an implementation-facing inventory and target pattern set.
