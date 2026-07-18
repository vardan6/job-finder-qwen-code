# Deep Gap Analysis: Remote Rover Parity (Job Finder)

## Overview
This document supplements the initial gap review by identifying deep functional and UX differences discovered through a direct analysis of the `remote-rover` source code (`ai.js`, `settings.js`, and `gcs_server` structure).

---

## 1. Advanced Chat UX & Productivity
| Feature | Description | Parity Priority |
| :--- | :--- | :--- |
| **Slash Command System** | Visual auto-complete menu triggered by `/`. Supports commands like `/context`, `/tool-activity`, and `/plan`. | **P1** |
| **Layout Persistence** | Draggable resizers for sidebar width and shell height. Values are stored in `localStorage`. | **P2** |
| **Rich Sidebar Metadata** | Session list items display the `last_message` preview and `updated_at` relative timestamps. | **P1** |
| **Inline Renaming** | Double-click session titles in the sidebar to rename them directly without a modal. | **P2** |
| **Copy Chat (Power User)** | "Copy as Markdown" button. Holding **Shift** or **Alt** includes hidden diagnostic blocks (tokens, latency, sources). | **P2** |

## 2. Multi-Model & Routing Sophistication
| Feature | Description | Parity Priority |
| :--- | :--- | :--- |
| **Advanced Fallback Editor** | Drag-and-drop or Up/Down controls for `fallback_provider_ids` per routing purpose. | **P0** |
| **Runtime Override Toggle** | UI control per routing purpose to allow/disallow manual model selection on the chat page. | **P1** |
| **Provider Table Actions** | Direct buttons in the list view for **Enable/Disable**, **Check Health**, and **Set as Default**. | **P0** |
| **Sortable Registry** | Column-based sorting (Name, Type, Status, Capabilities) for the provider table. | **P2** |
| **Template Expansion** | Templates for Gemini, LM Studio, Mistral, Together, Cohere, and HuggingFace. | **P1** |

## 3. Agent & Planning Intelligence
| Feature | Description | Parity Priority |
| :--- | :--- | :--- |
| **Interactive Approval UI** | Dedicated "Approval Cards" and "Clarification Cards" that allow the agent to pause and wait for user input. | **P1** |
| **In-flight Recovery** | The shell can reconnect to or resume an active stream if the page is reloaded during generation. | **P1** |
| **Tool Discovery (`list_data_surfaces`)** | An architectural pattern where the agent explicitly queries its own available tools and data sources. | **P2** |
| **Trace Persistence** | The UI remembers which tool-activity or diagnostic blocks were expanded/collapsed by the user. | **P2** |

## 4. Systems & Accessibility
| Feature | Description | Parity Priority |
| :--- | :--- | :--- |
| **Text-to-Speech (TTS)** | Support for Kokoro local service or Browser Speech synthesis with auto-read and voice selection. | **P3** |
| **JSON Settings Import/Export** | Granular export/import of settings sections (Providers, Routing, AI Settings) via JSON. | **P2** |
| **Theme Management** | Dedicated Light/Dark/System theme controls with persistence. | **P2** |

---

## Technical Observations (For Implementation)
1. **Tooling:** Remote Rover uses `AbortController` per-session, allowing the user to stop one stream while starting another in a different session.
2. **State:** The `aiState` object in Remote Rover is significantly more detailed, tracking `messageActivityOpen` and `slashQueryState`.
3. **Markdown:** Remote Rover relies on `marked.js` and `highlight.js`. These are currently missing from Job Finder's `base.html`.
4. **Slash Commands:** The parsing logic in `ai.js` (using `parseSlashCommand`) supports two-word commands (e.g., `/capabilities brief`).
