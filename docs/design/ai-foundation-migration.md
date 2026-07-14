# AI Foundation Migration

## Goal

Replace the legacy `job-finder` LLM/chat setup with a copied-and-adapted AI
architecture from `remote-rover/gcs_server`, while keeping the two projects
 fully separate at runtime and in data ownership.

`remote-rover` is the implementation source to copy from. `job-finder`
receives its own local code, state, settings, and AI storage.

## Canonical direction

- The old `job-finder` provider/model configuration is legacy and should be
  replaced, not preserved as a parallel system.
- The `remote-rover` AI provider settings model becomes the canonical LLM
  configuration approach for this repository.
- The `remote-rover` session-based chat runtime becomes the canonical AI chat
  approach for this repository.
- Rover-specific tools, modes, graph/planning surfaces, map widgets, replay
  surfaces, and rover terminology must not be carried over.

## Phase 1 target

The first visible milestone should prioritize a testable GUI and working core
AI runtime:

1. Port provider settings backend/UI from `remote-rover`.
2. Port session-based AI chat UI/backend with persisted sessions.
3. Keep `Chat` and `Agent` modes visible in the UI.
4. Make `Agent` mode real tool-calling from day one, but with a narrow initial
   toolset.
5. Add optional candidate attachment and per-session source controls.

## Provider system

Phase 1 provider behavior should follow the `remote-rover` model closely.

- One configured provider entry equals one runnable model target.
- Preserve auth modes:
  - `env_var`
  - `stored_secret`
  - `none`
- Preserve provider capabilities as explicit metadata.
- Preserve provider-level test status and provider health checks.
- Preserve purpose-based routing.

Do not keep the legacy SQL provider/model tables as a second source of truth.

## Routing purposes

Internal routing keys for `job-finder`:

- `general_chat`
- `agent`
- `document_analysis`
- `candidate_analysis`
- `job_matching`

Human-facing labels should be used in the UI while keeping the keys stable.

## Sessions

The primary AI unit is the chat session.

- One AI chat page with many saved sessions in a sidebar.
- Sessions are general by default.
- Sessions may optionally attach a candidate.
- Candidate attachment is explicit, session-level, and sticky until changed.
- Candidate attachment should be manageable both from normal UI controls and
  slash commands.
- Opening AI from a candidate page may pre-attach that candidate for a new
  session, but existing sessions should not silently retarget.

## Source controls

Per-session source controls should be copied from the `remote-rover` pattern,
adapted to `job-finder`.

Initial sources:

- `candidate_profile`
- `candidate_job_titles`
- `candidate_skills`
- `candidate_documents`
- `job_preferences`
- `ai_chat_history`
- `settings_config`
- `workspace_files`

Default on:

- `candidate_profile`
- `candidate_job_titles`
- `candidate_skills`
- `candidate_documents`
- `workspace_files`

Default off:

- `job_preferences`
- `ai_chat_history`
- `settings_config`

When no candidate is attached, non-candidate sources remain available.

## Initial agent tool surface

Phase 1 agent mode should start with a narrow real tool catalog:

- candidate/profile lookup
- skills lookup
- preferred titles lookup
- documents listing/reading
- preferences lookup
- chat-history lookup
- settings/provider/routing lookup
- workspace file read/write

`jobs/search_results` is intentionally out of the initial AI surface.

## Agent runtime migration

Agent mode should use `backend.ai_agent` as the model-facing runtime boundary.
The typed registry owns model-visible tool contracts, JSON schemas, permission
classes, scopes, and validation before handler execution. Direct HTTP tool
execution through `backend.ai_tool_registry` may remain as a lower-level
adapter while the server-side model-driven loop is built.

The first model-visible read tools are:

- `list_data_surfaces`
- `candidate_skills_lookup`

`list_data_surfaces` is the discovery tool for lazy context loading. It should
return compact metadata about attached candidate data, chat history, workspace
files, and redacted settings availability rather than loading full records into
the prompt.

## Mutation policy

Mutation policy should be configurable at the AI settings level.

Initial modes:

- `read_only`
- `approve_writes`
- `auto_allow_ai_owned_files`

Recommended initial default: `approve_writes`.

Desired behavior:

- read tools execute immediately
- tool usage is generally free
- overwriting or mutating important state should require approval
- AI-owned output files may be allowed more directly depending on policy

## Existing AI-backed features

Existing AI-backed features in `job-finder` should move onto the new provider
and routing system instead of preserving a dual-track setup.

This includes features such as candidate-document analysis, title extraction,
skill extraction, and matching-related AI flows.
