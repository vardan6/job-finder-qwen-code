# Design — Agent-Mode Provider Capabilities (Q6 resolution)

Decided 2026-07-19 with maintainer. Governs the deferred Phase 10 agent
runtime ("Enforce provider tool-calling capability/fallback" slice).

## Decisions

1. **Capabilities attach per model, not per provider.** A provider entry
   lists models, each with its own capability set (`chat`/`tools`/`vision`/
   `reasoning`). Flat provider-level capabilities in `ai_capabilities.py`
   migrate to model-level.
2. **Capabilities are verified, not just declared.** A verification probe
   (small tool-bound call) runs per model — on demand from the settings UI
   and on first agent use — storing `verified_at` + result alongside the
   declared flags. Declared-but-unverified counts as "unknown", not "yes".
3. **Fallback behavior (informed by remote-rover, then improved):**
   - Reference behavior (`gcs_server/ai/chat_service.py:869`,
     `agent_loop.py:159/335`): no upfront capability routing — it attempts
     the tool-bound call and sniffs the error message ("does not support
     tools/function calling"); on match, the agent loop returns `None` and
     the caller silently degrades that turn to plain non-tool generation.
   - Job-finder adopts the same **runtime error detection as a safety net**
     but adds what the reference lacks:
     a. **Route first**: agent mode resolves the routing chain and skips
        models whose verified capability says no-tools (no wasted call).
     b. **Degrade visibly**: if a runtime unsupported error still occurs,
        fall back to plain chat for that turn AND emit a user-visible notice
        ("provider X can't run tools — answered without tools") plus a trace
        event; never silently.
     c. Persist the runtime finding: an unsupported error marks the model's
        verified tools-capability false, so routing skips it next time.

## Rationale

Per-model is factual reality (one Ollama model supports tools, another not).
Probing beats trusting checkboxes (users guess wrong). The reference's silent
degrade hides failures — visible degrade + capability memory keeps agent mode
predictable without hard-failing the chat.
