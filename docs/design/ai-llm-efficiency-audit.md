# LLM Efficiency Audit — best-practice coverage

> Audit of the AI/LLM call path against standard latency/token best practices.
> Verb "flag" not "fix": this records what is implemented, what is missing, and
> the impact — no behavior changed. Verified against code on 2026-07-21.
> Reference impl `remote-rover` was checked too: it also lacks these, so nothing
> was dropped in the port — the practices were simply never adopted.

## Where LLM calls are built (the chokepoints)

Every LLM call funnels through `backend/services/llm_service.py`:

- `_build_completion_kwargs()` — shared builder used by `call_llm`,
  `extract_skills_from_text`, and `routes/chat.py` (chat + stream). Sets **only**
  `model`, `messages`, `temperature` (+ `api_base`/`api_key`).
- `send_message()` — builds kwargs inline for `document_parser`,
  `job_title_parser`; same three fields.

So two functions gate almost all token/latency behavior. Fixing them is central,
not scattered.

## Coverage table

| Best practice | Status | Evidence / impact |
| --- | --- | --- |
| Async non-blocking calls (`acompletion`) | ✅ done | `llm_service.py`; keeps event loop free |
| Dedicated LLM thread pool | ✅ done | `services/llm_executor.py` (isolation, not speed) |
| Streaming responses | ✅ done | `routes/chat.py` stream; improves *perceived* latency |
| Timeouts on every call | ✅ done | `LLM_TIMEOUT=120s`, `LLM_CHAT_TIMEOUT=180s` |
| LiteLLM pre-import at startup | ✅ done | `app.py:98`; avoids 10–30s first-call stall |
| History truncation | ✅ partial | last 10 msgs (`chat.py:291`); crude, no token budget |
| Task-level result cache | ✅ narrow | file cache in `job_analysis.py` only |
| **Prompt / context caching** | ❌ **missing** | no `cache_control`, no `litellm.cache`; full system+context+history re-billed every turn |
| **Ollama `keep_alive`** | ❌ **missing** | default model is `ollama/llama3`; model unloads+reloads each call → biggest local latency cause |
| **`max_tokens` cap** | ❌ missing | unbounded output = slower + more tokens than needed |
| **HTTP connection reuse** | ❌ unverified | no persistent httpx/AsyncClient configured; risk of fresh TLS per call |
| **Lazy context loading** | ❌ missing | full candidate profile injected every turn (`_build_session_system_context`); Phase 6 lazy tools fix this |
| **General/semantic response cache** | ❌ missing | `REDIS_URL` in config but unused for LLM |
| **`response_format` / JSON mode** | ❌ missing | parsers regex-scrape JSON from prose (`extract_json_from_response`); retries on malformed output waste a full call |
| **Structured token/cost telemetry** | ⚠️ partial | usage captured per message meta, but not aggregated; no cache-hit visibility |

## The two misconceptions worth stating plainly

1. **"Session" is not an efficiency feature.** `ai_session_store` is conversation
   *persistence*. On its own it makes calls *more* expensive — every turn replays
   history. The feature that makes reused context cheap is **prompt caching**, a
   different mechanism we do not have.
2. **These gaps are not a regression.** The reference `remote-rover` lacks them
   too. This is greenfield efficiency work, not a repair.

## Prioritized recommendations

**Tier 1 — quick, safe, central (biggest felt latency):**
1. Ollama `keep_alive` (e.g. `"30m"`) in `_build_completion_kwargs` — stops
   reload-per-call on the default local model.
2. `max_tokens` cap (config-driven) — bounds output cost/latency everywhere.
3. Verify/enable LiteLLM HTTP client reuse.

**Tier 2 — larger token wins, deliberate slices:**
4. Provider-aware **prompt caching** (Anthropic `cache_control` breakpoints on
   the stable system+context prefix; auto for OpenAI/Gemini). Pairs with keeping
   the cached prefix stable across turns.
5. **JSON mode / `response_format`** for the parser call sites to kill
   scrape-and-retry waste.
6. **Lazy context** — the Phase 6 `AIContextService` change; stop pre-injecting
   full candidate data.

**Tier 3 — infra:**
7. Optional Redis-backed response/semantic cache for repeated analytical calls.
8. Token/cost + cache-hit aggregation for visibility.

## Suggested roadmap placement

Tier 1 is independent of the deferred agent-loop work and can be its own small
slice. Tiers 2–3 should be captured as ordered slices alongside the Phase 6
planning (prompt caching + lazy context naturally co-design with
`AIContextService`). None of this is in `roadmap.md` yet — it needs a
planning-capture pass to become "complete the roadmap ⇒ efficiency done."
