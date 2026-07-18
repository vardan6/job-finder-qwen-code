# AI Agent Architecture Plan

Date: 2026-06-04

## Decision

Job-finder should pause Phase 6 polish long enough to add a real server-side
agent runtime. The current `agent` mode is a UI/trace placeholder: it streams a
normal chat completion with eager context and synthetic tool activity events.
It does not pass typed tools to the model, does not let the model choose tools,
and does not run an iterative model -> tool -> result -> model loop.

The target architecture is:

```text
user prompt
  -> session + run mode + selected source controls
  -> compact always-on context + data access manifest
  -> provider-capability-aware agent loop
  -> model chooses typed tools on demand
  -> server validates args, applies policy, executes tools, records trace
  -> tool results feed back through the model tool-call protocol
  -> final answer, clarification request, approval request, or safe fallback
  -> persisted transcript + trace + loaded-data refs/citations
```

This is the right tradeoff because it keeps prompts small, makes tool use
auditable, respects source controls, and lets the assistant load candidate
profile, documents, jobs, chat history, settings, and workspace files only when
the current question needs them.

## Current Baseline

Useful foundations already exist:

- Persisted AI sessions and streaming chat endpoints:
  `job-finder-web/backend/routes/chat.py`.
- Model/provider routing:
  `job-finder-web/backend/services/ai_routing.py`.
- Source controls and attached candidate state:
  `job-finder-web/backend/ai_session_store.py`.
- Basic tool registry:
  `job-finder-web/backend/ai_tool_registry.py`.
- Direct HTTP tool list/execute routes:
  `job-finder-web/backend/routes/ai_tools.py`.
- Frontend rendering for stream traces, diagnostics, approvals, and tool
  activity:
  `job-finder-web/frontend/templates/chat.html`.

Material gaps:

- No model-bound tool schemas are sent with the LLM request.
- No iterative agent loop exists.
- Tool definitions are thin dictionaries, not typed contracts.
- Source controls do not decide which tools are exposed to the model.
- Candidate context is partly prompt-preloaded instead of discovered lazily.
- Approval exists for direct HTTP tool execution, not model-driven tool calls.
- Trace/tool activity is not backed by a persisted trace store.
- Provider routing does not enforce tool-calling capability for agent mode.

## Non-Goals For The First Agent Runtime

- Do not introduce MCP as the first implementation. Keep the registry local,
  then add an MCP adapter later if useful.
- Do not build vector/RAG first. Deterministic read tools solve the immediate
  candidate/profile/job/settings use cases with lower risk.
- Do not support write tools in the first slice. Start read-only, then add
  approval/resume.
- Do not rewrite the whole chat UI. Reuse the current streaming and activity
  surfaces, replacing synthetic events with real trace events.
- Do not silently degrade agent mode to plain chat. If tools are unavailable,
  make the fallback explicit.

## Architecture Components

### 1. Agent Runtime

Add:

```text
job-finder-web/backend/ai_agent/
  __init__.py
  agent_loop.py
  context_service.py
  policy_engine.py
  schemas.py
  tool_registry.py
  trace_store.py
```

Minimum loop behavior:

```text
prepare compact context snapshot
prepare data access manifest
select allowed tools from source controls + policy
resolve provider/model with tool-calling capability
for iteration in 1..max_iterations:
  call model with messages + typed tools
  if no tool calls: persist final answer and stop
  for each tool call:
    validate args against schema
    run policy
    execute handler
    persist trace event
    append tool result message
return final answer or explicit stop reason
```

Required stop reasons:

- `final_answer`
- `tool_call_validation_failed`
- `tool_execution_failed`
- `repeated_tool_failure`
- `iteration_limit`
- `clarification_requested`
- `approval_required`
- `provider_lacks_tool_calling`

### 2. Typed Tool Registry

Replace thin tool dictionaries with structured definitions:

```python
ToolDefinition(
    name="candidate_skills_lookup",
    description="Read normalized skill records for the attached candidate.",
    permission="read",
    tier=1,
    required_scopes=frozenset({"candidate:read"}),
    side_effects=frozenset(),
    input_schema={...},
    output_schema={...},
    handler=...,
    is_terminal=False,
)
```

Every tool needs:

- JSON input schema.
- Stable output schema.
- Permission class: `read`, `draft`, `write`, or `external`.
- Required scopes/source controls.
- Result size limits and summary behavior.
- Redaction policy for trace storage.
- Stable error shape.

### 3. Context Service

Move context construction out of `routes/chat.py` into an `AIContextService`.

Always-on context should stay compact:

- session ID/title/run mode;
- attached candidate ID/name only;
- enabled source controls;
- provider/model summary;
- short instruction that deeper data is available through tools.

Lazy deterministic tools should load:

- candidate profile;
- titles;
- skills;
- preferences;
- document list;
- parsed document snippet/read by ID;
- jobs/applications/employers with filters and limits;
- redacted settings;
- chat session list/search/read;
- workspace file list/read.

Large text and semantic recall should wait for a later retrieval phase.

### 4. Data Access Manifest

Add `list_data_surfaces` as the first model-visible discovery tool. It should
return compact metadata, not full data:

```json
{
  "candidate": {
    "attached_candidate_id": 12,
    "available": ["profile", "job_titles", "skills", "documents"]
  },
  "chat_history": {
    "current_session_id": "abc",
    "search_available": true
  },
  "workspace_files": {
    "read_available": true,
    "write_requires_approval": true
  },
  "settings": {
    "redacted_provider_config_available": true
  }
}
```

The manifest is the key to lazy loading: the model can see what exists without
spending tokens on every candidate file or history item.

### 5. Policy And Approval

Tool classes:

- `read`: runs when source controls and scopes allow it.
- `draft`: can generate proposed artifacts but cannot mutate durable state.
- `write`: requires explicit user approval.
- `external`: requires explicit user approval and stronger confirmation.

First runtime milestone should support only `read`. Approval/resume should be a
separate milestone using pending-run state and the existing frontend approval
cards.

### 6. Trace Store

Persist real trace events instead of only streaming synthetic activity.

Trace events should record:

- run start/end;
- provider/model and routing decision;
- context snapshot ID;
- exposed tools;
- model tool calls;
- validated/redacted args;
- policy decisions;
- tool result summaries/errors;
- stop reason;
- latency and token usage when available.

Assistant message metadata should include `trace_id`, `loaded_data_refs`, and
retrieval/citation placeholders even before RAG exists.

### 7. Provider Capability Handling

Agent mode must require a tool-capable provider. Routing should track:

- supports tool calling;
- supports streaming tool calls;
- supports structured outputs;
- supports parallel tool calls;
- max context window;
- preferred JSON/schema mode.

If the selected provider lacks tool calling, agent mode should either route to a
tool-capable fallback for the agent purpose or return an explicit degraded-mode
notice. It should not pretend that tools were checked.

## Implementation Plan

### Phase A - Read-Only Agent Runtime Skeleton

Goal: one real model-driven read-only tool call.

Tasks:

- Add `ai_agent/schemas.py` with `ToolDefinition`, `ToolCallResult`,
  `AgentRunResult`, and stop reason types.
- Add `ai_agent/tool_registry.py` and port the existing candidate profile,
  titles, skills, and `list_data_surfaces` handlers.
- Add `ai_agent/context_service.py` for compact session/candidate/source-control
  context.
- Add `ai_agent/agent_loop.py` with max iteration guard and one LiteLLM
  tool-calling path.
- Wire `run_mode=agent` in `routes/chat.py` to the agent loop.
- Stream real tool-call/tool-result trace events to the existing chat frontend.
- Persist the final answer and minimal trace metadata in assistant message
  metadata.

Acceptance criteria:

- Asking "What are this candidate's strongest skills?" with an attached
  candidate sends only compact candidate identity in the initial context.
- The model calls `candidate_skills_lookup`.
- The answer uses the tool result.
- A trace event records the tool name, validated args, result summary, and stop
  reason.
- If the provider does not support tools, the response explicitly says agent
  tools are unavailable or routes to a configured tool-capable fallback.

Focused tests:

- `run_mode=agent` invokes the agent loop, not the plain chat completion path.
- Disabled/unsupported tool capability returns `provider_lacks_tool_calling`.
- Tool args are schema-validated before handler execution.
- Iteration limit prevents runaway loops.

### Phase B - Source-Control-Gated Lazy Context

Goal: source controls decide which tools the model can see.

Tasks:

- Map session source controls to allowed tool scopes.
- Hide disabled tools before model invocation.
- Add document list/read tools with size limits.
- Add loaded-data refs to assistant metadata.
- Add tests proving disabled tools are not exposed and cannot be called.

Acceptance criteria:

- Disable candidate documents in source controls.
- Ask about resume text.
- The model does not see document tools and cannot call them.
- Re-enable documents and verify document lookup/read happens lazily.

### Phase C - Persistent Trace Store

Goal: every agent answer is inspectable and reproducible.

Tasks:

- Add `trace_store.py` backed by the same persistence style as AI sessions.
- Persist run, model, tool, policy, error, and stop events.
- Add `trace_id` to assistant metadata.
- Add `GET /api/ai/traces/{trace_id}`.
- Render persisted trace details from the existing UI affordances.

Acceptance criteria:

- A failed tool call appears in the trace with redacted args/output, error
  shape, policy decision, and stop reason.
- Retrying a message produces a new trace linked to the retried assistant turn.

### Phase D - Approval And Resume

Goal: model-driven draft/write tools can pause safely and resume.

Tasks:

- Add pending agent run storage.
- Add policy decisions for `draft`, `write`, and `external`.
- Convert write-tool requests into approval card payloads.
- Add resume endpoint with decisions: approve, edit args, reject.
- Keep workspace writes and candidate mutations behind this gate.

Acceptance criteria:

- Agent proposes writing a cover letter file.
- Run pauses before the write.
- User approval executes the tool and resumes the agent.
- Rejecting the approval records the decision and lets the model answer with a
  safe alternative.

### Phase E - Retrieval For Large Text

Goal: semantic retrieval for large documents and long chat history.

Tasks:

- Chunk parsed candidate documents.
- Add vector store abstraction.
- Add embedding-provider routing.
- Add metadata-filtered retrieval tools.
- Add citations into answer metadata.
- Add rebuild/reindex controls.

Acceptance criteria:

- Asking about a detail buried in a long resume uses retrieval chunks rather
  than loading the whole document.
- The answer records loaded chunk/document citations.

## First Three Atomic Slices

1. Create `ai_agent/schemas.py` and typed read-only tool definitions for
   `list_data_surfaces` and `candidate_skills_lookup`, with unit tests for
   schema validation.
2. Add `AIContextService` and update `routes/chat.py` so `run_mode=agent`
   builds compact context through the service while plain chat behavior remains
   unchanged.
3. Add the first `AgentLoopRuntime` path with a mocked/model-stub test proving
   model tool calls execute `candidate_skills_lookup` and return a final answer.

These slices are intentionally small. They establish the runtime seam before
expanding tools, tracing, approval, or retrieval.

## Roadmap Impact

Recommended roadmap change:

- Insert a new Phase 6 item before polish:
  `Add real read-only model-driven agent runtime with typed tools and trace
  events`.
- Move current Phase 6 polish items down unchanged.
- Treat approval/resume and RAG as later phases unless the first runtime slice
  proves too small for user needs.

## Review Checklist

Before merging the runtime work, verify:

- Agent mode has a distinct backend execution path.
- Tool schemas are typed and validated.
- Source controls gate tool exposure.
- The model receives a manifest, not eager large context.
- Tool outputs are returned through tool-call protocol messages.
- Stop reasons are explicit and tested.
- Provider capability fallback is explicit.
- Trace metadata is persisted enough to debug a bad answer.
- No write/external tool can execute without approval.

## References Used

- OpenAI function calling and tools documentation:
  https://platform.openai.com/docs/guides/function-calling
- OpenAI Structured Outputs documentation:
  https://platform.openai.com/docs/guides/structured-outputs
- OpenAI Agents SDK documentation:
  https://platform.openai.com/docs/guides/agents-sdk/
- OpenAI Agents SDK tracing documentation:
  https://openai.github.io/openai-agents-python/tracing/
- OpenAI retrieval documentation:
  https://platform.openai.com/docs/guides/retrieval
- LangGraph persistence documentation:
  https://docs.langchain.com/oss/python/langgraph/persistence
- LangChain/LangGraph human-in-the-loop documentation:
  https://docs.langchain.com/oss/python/langchain/human-in-the-loop
- Anthropic tool use reference:
  https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-reference
- Model Context Protocol tools specification:
  https://modelcontextprotocol.io/specification/draft/server/tools
