# Enhanced Handoff: Remote Rover Gap Review (LLM Providers + AI Chat)

## Overview
This document enhances the initial gap review from 2026-05-31. It provides specific technical implementation paths, file references, and risk assessments to accelerate the "Remote Rover" parity phase.

## Technical Baseline
- **Configuration:** `backend/ai_config_store.py` (handles `ai-settings.json` persistence).
- **Routing Logic:** `backend/services/ai_routing.py` (already supports `fallback_provider_ids` but lacks UI).
- **Chat State:** `backend/ai_session_store.py` (handles persisted AI sessions).
- **Frontend Templates:** `frontend/templates/settings/llm.html` and `frontend/templates/chat.html`.

---

## 1. LLM Providers Page (Settings)

### Gaps & Actionable Implementation
| Feature | Implementation Notes | Target File(s) | Complexity |
| :--- | :--- | :--- | :--- |
| **Fallback Routing Editor** | Replace the static text in `#routing-editor` with a multi-select or sortable list for `fallback_provider_ids`. | `llm.html` (JS), `ai_config_store.py` | Medium |
| **Provider Health Checks** | Add a `Check` button to each row. Requires a new backend endpoint `/api/llm/check/{provider_id}` that attempts a trivial completion. | `llm.html`, `routes/llm_config.py` | Low |
| **Quick Toggle Actions** | Add a "Power" icon in the table rows for immediate `enabled: true/false` updates without opening the full editor. | `llm.html` | Low |
| **Template Expansion** | Add remaining Remote Rover templates (Gemini, LM Studio, etc.) to the `PROVIDER_TEMPLATES` JS constant. | `llm.html` | Low |
| **Sortable Table** | Implement client-side sorting for the provider table using a small helper or library-free JS. | `llm.html` | Low |
| **Default Provider Action** | Add a "Set as Default" button in the table that updates `general_chat` routing in one click. | `llm.html` | Low |

---

## 2. AI Chat Page

### Gaps & Actionable Implementation
| Feature | Implementation Notes | Target File(s) | Complexity |
| :--- | :--- | :--- | :--- |
| **Markdown Rendering** | **Critical:** Replace the current `.replace(/\n/g, '<br>')` with a robust markdown library (e.g., `marked.js`) and `highlight.js` for code blocks. | `chat.html`, `chat.css` | High |
| **Run Mode Controls** | Add a toggle/pill selector in `#activeModelSummary` for `Chat / Agent / Intent / Planning`. Update the `/api/chat/stream` call to include `mode`. | `chat.html`, `chat.py` | Medium |
| **Stop Streaming** | Implement an `AbortController` in `sendMessage` and expose a "Stop" button that appears only during active streaming. | `chat.html` | Low |
| **Agent Trace UI** | Create a sub-component within assistant messages to render tool calls, thinking blocks, and trace logs (needs backend event support). | `chat.html`, `ai_routing.py` | High |
| **Context Diagnostics** | Display token usage and retrieved source summaries in a collapsible "Diagnostics" section at the bottom of assistant bubbles. | `chat.html` | Medium |
| **Archived Search** | Add a text input to the sidebar to filter `sessionList` and a toggle to show/hide archived sessions. | `chat.html` | Low |
| **Copy as Markdown** | A button in the header that iterates through `messagesContainer` and generates a single MD string of the full conversation. | `chat.html` | Low |

---

## 3. Recommended Execution Slices

### Slice 1: Configuration Hygiene (P0)
- **Goal:** Enable fallback routing and provider health.
- **Tasks:**
  1. Add `/api/llm/check/{provider_id}` endpoint.
  2. Implement health check UI in `llm.html`.
  3. Add the fallback provider selector to the routing editor.

### Slice 2: Chat Robustness (P0)
- **Goal:** Professional-grade rendering and control.
- **Tasks:**
  1. Integrate `marked.js` and `highlight.js` for assistant replies.
  2. Implement "Stop Streaming" with `AbortController`.
  3. Add per-message "Retry" logic (already partially present, needs refinement for specific models).

### Slice 3: Agent Visibility (P1)
- **Goal:** Transparency for complex AI tasks.
- **Tasks:**
  1. Add "Run Mode" (Agent vs Chat) selection.
  2. Implement Tool/Trace rendering in the chat bubbles.
  3. Add Token/Context diagnostics.

## Strategic Notes
- **Dependencies:** `marked.js` and `highlight.js` should be added via CDN or local vendor files to avoid a build step for now, maintaining the "Vanilla" philosophy.
- **State Management:** The current `chat.html` uses a single `state` object and global functions. As complexity grows (Agent traces, etc.), consider a slightly more modular structure for message components.
- **Abort Logic:** Ensure the backend handles aborted connections gracefully to avoid orphan LLM requests.
