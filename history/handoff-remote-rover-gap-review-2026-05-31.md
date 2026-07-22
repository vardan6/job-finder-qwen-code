# Handoff: Remote Rover Gap Review (LLM Providers + AI Chat)

## Session intent
User asked for a fresh comparison against `remote-rover` because current pages are missing significant pieces. Requested order: start from LLM providers/settings page, then AI chat page.

## Compared code
- Source baseline:
  - `/mnt/c/Users/vardana/Documents/Proj/remote-rover/gcs_server/static/settings.html`
  - `/mnt/c/Users/vardana/Documents/Proj/remote-rover/gcs_server/static/settings.js`
  - `/mnt/c/Users/vardana/Documents/Proj/remote-rover/gcs_server/static/ai.html`
  - `/mnt/c/Users/vardana/Documents/Proj/remote-rover/gcs_server/static/ai.js`
- Current project:
  - `/mnt/c/Users/vardana/Documents/Proj/job-finder-app/job-finder-web/frontend/templates/settings/llm.html`
  - `/mnt/c/Users/vardana/Documents/Proj/job-finder-app/job-finder-web/frontend/templates/chat.html`

## Findings summary
No code changes were made. This was a review-only pass.

### LLM Providers page gaps
1. Missing provider health checks in UI:
- No `Check Draft` and no per-provider `check` action equivalents.
2. Missing fallback routing editor:
- Only primary provider selection is implemented; ordered fallback add/remove/reorder is absent.
3. Missing “set default provider” quick action:
- Remote Rover supports setting `general_chat` default directly from provider list.
4. Missing sortable provider table:
- Remote Rover supports column sorting state; current table is static.
5. Narrower template coverage:
- Missing several Remote Rover templates (e.g., `google_gemini`, `lm_studio`, `mistral`, `cohere`, `together`, `huggingface`).
6. Missing explicit cancel-edit control:
- Current page has New/Delete but no dedicated cancel-edit flow.
7. Missing per-provider quick enable/disable action:
- Remote Rover provider rows include direct enable/disable action controls; current page requires editing via the form checkbox.
8. Missing runtime-override routing control:
- No UI for per-purpose `allow_runtime_override` in routing rules.
9. Missing dedicated routing save/reload controls:
- Remote Rover has routing-specific save/reload/status controls; current page only has one combined save flow.

### AI Chat page gaps
1. Missing run mode controls:
- No `chat / agent / intent / planning_shell` mode toggle set.
2. Missing agent tool/trace activity rendering:
- No tool-call timeline, status, or trace blocks per assistant message.
3. Missing context/retrieval diagnostics:
- No context-budget and retrieved-source detail blocks on assistant messages.
4. Missing archived sessions filter + search:
- No active/archived toggle and no session search control.
5. Missing routing-default provider selector behavior:
- Current UX is model picker oriented; lacks Remote Rover routing-default semantics.
6. Missing stop-stream action:
- No “Stop” control during streaming response.
7. Missing full-chat copy action:
- No “copy chat as markdown” control.
8. Missing Remote Rover shell layout extras:
- No split resizers/map-area integration.
9. Missing composer-level retry response control:
- Remote Rover provides a dedicated “Retry response” composer action for the latest model response.
10. Missing slash-command + local command fallback flow:
- Remote Rover supports local command responses (e.g., `/context`, `/retrieval-surfaces`, `/tool-activity`, `/tools`) when server-side command support is unavailable.
11. Missing markdown + code rendering stack:
- No sanitized markdown rendering, syntax-highlighted code blocks, or per-code-block copy controls.
12. Missing in-flight stream recovery:
- No persisted in-flight marker and stream-status recovery logic across reloads/session switches.
13. Missing planning-shell suspension/approval interaction flow:
- UI/state for suspended planning runs and approval handoff handling is absent.

## Suggested next execution order
1. LLM settings parity slice (P0): fallback routing editor + save/reload + provider checks.
2. LLM settings parity slice (P1): default-provider quick action + provider sorting + template expansion + cancel-edit + per-row enable/disable + runtime-override control.
3. Chat parity slice (P0): run modes + stop-stream + archived/search sessions + composer retry.
4. Chat parity slice (P1): agent tool/trace UI + context/retrieval diagnostics + slash-command/local fallback support.
5. Chat parity slice (P2): copy-chat markdown + markdown/code renderer + in-flight stream recovery + planning-shell approval/suspension handling + layout resizers/shell extras as appropriate for job-finder domain.

## Constraints and notes
- `roadmap.md` currently has all items checked; project context indicates “Roadmap reset needed.”
- Before implementation, add a new unchecked roadmap item for this parity work, then continue with `/next-slice` per project workflow.

## Recommended skills for next session
- `/session-open` (mandatory first step)
- `/next-slice` (pick one atomic implementation slice)
- `/session-close` (after each completed step)
- `/doc-update` (only if non-trivial durable docs need updates)
