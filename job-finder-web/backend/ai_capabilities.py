from __future__ import annotations

ROUTING_PURPOSES = (
    "general_chat",
    "agent",
    "document_analysis",
    "candidate_analysis",
    "job_matching",
)

ROUTING_PURPOSE_LABELS = {
    "general_chat": "General Chat",
    "agent": "Agent",
    "document_analysis": "Document Analysis",
    "candidate_analysis": "Candidate Analysis",
    "job_matching": "Job Matching",
}

PROVIDER_CAPABILITIES = (
    "chat",
    "tools",
    "vision",
    "reasoning",
)

SESSION_MODES = (
    "general_chat",
    "agent",
)

SESSION_MODE_LABELS = {
    "general_chat": "General Chat",
    "agent": "Agent",
}

JOB_FINDER_TOOL_CAPABILITIES = (
    "candidate_profile_lookup",
    "candidate_titles_lookup",
    "candidate_skills_lookup",
    "candidate_documents_lookup",
    "candidate_preferences_lookup",
    "chat_history_lookup",
    "settings_lookup",
    "workspace_files_read",
    "workspace_files_write",
)
