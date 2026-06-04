# Merged Handoff: Remote-Rover Parity (LLM Settings + AI Chat)

## Scope
Consolidated from:
- `handoff-remote-rover-gap-review-2026-05-31.md`
- `handoff-review-2026-05-31.md`
- `handoff-deep-gap-analysis-2026-05-31.md`

This merged handoff is the canonical parity backlog and execution order.

## Normalized Gap Backlog

### P0 (Do first)
1. Routing fallback editor in LLM settings (`fallback_provider_ids`, ordered).
2. Provider row quick actions:
   - enable/disable
   - health check
   - set as default for `general_chat`
3. Chat stop-stream control with `AbortController`.
4. Archived sessions support in chat sidebar (filter/toggle + load behavior).

### P1 (High value next)
1. Runtime override toggle per routing purpose (`allow_runtime_override`).
2. Template expansion (Gemini, LM Studio, Mistral, Together, Cohere, HuggingFace).
3. Chat run modes (`chat / agent / intent / planning_shell`).
4. Slash command UX and local fallback (`/context`, `/tool-activity`, `/plan`, etc.).
5. Agent tool/trace activity rendering.
6. Context/retrieval diagnostics blocks.
7. In-flight stream recovery across reload/session switch.
8. Interactive approval/clarification cards for suspended runs.

### P2 (Quality/UX parity)
1. Sortable provider table.
2. Routing-specific save/reload controls and clearer status messaging.
3. Cancel-edit flow in provider editor.
4. Inline session rename (double-click title).
5. Copy full chat as markdown (power mode variants can follow).
6. Trace expansion persistence in UI state.
7. Layout persistence (resizers, localStorage).
8. JSON settings import/export.
9. Theme management controls.
10. Tool discovery surface (`list_data_surfaces` pattern) where appropriate.

### P3 (Optional / later)
1. Text-to-speech support (browser speech or local service).

## Duplicate Reconciliation Notes
- `Rich sidebar metadata` (last message + updated timestamp) is already implemented in current `chat.html` and is not listed as a new roadmap item.
- `Per-message retry` exists; keep only refinement tasks when tied to run-mode and stream-control work.
- Markdown/code rendering is elevated as a cross-cutting robustness item (security + usability), but staged after P0 controls.

## Technical Baseline Confirmed
- Routing persistence exists in `backend/ai_config_store.py`.
- Runtime routing logic exists in `backend/services/ai_routing.py` and already reads fallback config.
- Session persistence exists in `backend/ai_session_store.py`.
- Active frontend surfaces:
  - `frontend/templates/settings/llm.html`
  - `frontend/templates/chat.html`

## Execution Strategy
1. Finish all P0 slices as independently shippable verticals.
2. Land P1 visibility/control slices in small increments (one UI behavior + one API shape at a time).
3. Use P2 for polish after core routing/chat-operability parity is stable.
4. Keep each slice verifiable with one command or one obvious manual check path.
