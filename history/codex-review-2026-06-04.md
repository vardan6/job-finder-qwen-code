# Codex Review - 2026-06-04

## Findings

### Must fix now

1. **Explicit DB model selection can drop working credentials**

   In `job-finder-web/backend/services/ai_routing.py:170`, explicit DB model selection prefers a JSON-config match even when that config has no usable credentials because `_selection_from_provider_cfg(..., require_credentials=False)` is used at `job-finder-web/backend/services/ai_routing.py:179`.

   Risk: a working DB-backed provider can be downgraded into an unauthenticated runtime provider and fail chat unexpectedly.

2. **Stop-stream is not handled cleanly server-side**

   Stop-stream is only handled on the browser side in `job-finder-web/frontend/templates/chat.html:462`, but the server stream loop in `job-finder-web/backend/routes/chat.py:684` does not handle disconnect or cancellation explicitly, and the user turn is persisted before completion at `job-finder-web/backend/routes/chat.py:669`.

   Risk: aborts and timeouts can leave orphaned user turns and may continue upstream generation after the client stops listening.

### Should fix before phase complete

1. **Anthropic template model ID is stale**

   The Anthropic template in `job-finder-web/frontend/templates/settings/llm.html:328` ships `claude-sonnet-4-0`.

   Anthropic’s current official docs examples use dated Claude 4 IDs like `claude-sonnet-4-20250514`, so this template is stale and likely to break sooner than later.

2. **Secrets are plaintext and secret endpoints are open**

   Secrets are stored in plaintext in `job-finder-web/backend/ai_secret_store.py:33`, and secret mutation endpoints in `job-finder-web/backend/routes/ai_secrets.py:11` are unauthenticated.

   This is only acceptable for a strictly local single-user app. It is not a safe boundary if the app is ever exposed or synced.

3. **Two provider systems are still active**

   There are still two provider systems alive: legacy DB-backed CRUD in `job-finder-web/backend/routes/llm_config.py:131` and the JSON-backed canonical store in `job-finder-web/backend/ai_config_store.py:142`.

   This drift is already visible in routing and model-selection code and will keep creating edge cases until one source of truth is removed.

### Backlog

1. **Connectivity test route can report the wrong model**

   The connectivity test route in `job-finder-web/backend/routes/llm_test.py:45` defaults `model` before resolving `provider_id`, so provider-based tests can log and return the wrong model label and skip the right Ollama preflight path.

2. **Workflow state files are stale**

   `activeContext.md` and `roadmap.md` still say the sortable provider registry table is next, but the table and sortable headers already exist in `job-finder-web/frontend/templates/settings/llm.html:265`.

   This should be cleaned up at the next `/session-close`.

## Web-researched best practices

1. **OpenAI default model guidance has moved on**

   OpenAI’s current docs recommend starting with `gpt-5-mini` for newer work, while the templates still default OpenAI and OpenRouter to `gpt-4.1-mini`.

   This is an enhancement rather than a bug, but it is worth updating defaults for new installs.

   Sources:
   - https://platform.openai.com/docs/models
   - https://platform.openai.com/docs/models/gpt-5-mini

2. **Anthropic docs use dated Claude 4 IDs**

   Anthropic’s official docs examples now show dated Claude 4 model IDs rather than the template’s generic `claude-sonnet-4-0`, which reinforces updating that template now.

   Sources:
   - https://docs.anthropic.com/en/docs/claude-code/cli-usage
   - https://docs.anthropic.com/pt/api/handling-stop-reasons

## Validation and gaps

- `python3 -m pytest` could not be run because `pytest` is not installed in the local `python3` environment.
- `python3 -m compileall` across `job-finder-web/backend` and `job-finder-web/tests` passed.
- The largest remaining test gaps are abort/disconnect behavior for streaming and the explicit-model-plus-missing-credentials path.
