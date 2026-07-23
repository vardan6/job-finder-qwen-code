from __future__ import annotations

from enum import Enum


class Purpose(str, Enum):
    """Canonical routing purposes. Compares/hashes as its string value."""

    GENERAL_CHAT = "general_chat"
    AGENT = "agent"
    DOCUMENT_ANALYSIS = "document_analysis"
    CANDIDATE_ANALYSIS = "candidate_analysis"
    JOB_MATCHING = "job_matching"

    def __str__(self) -> str:
        # Python 3.11+ changed str(Enum) to "Purpose.GENERAL_CHAT" even for
        # str-mixin enums; keep f-string interpolation matching the plain
        # string value everywhere purposes are logged or raised in errors.
        return self.value


ROUTING_PURPOSES = tuple(purpose.value for purpose in Purpose)

ROUTING_PURPOSE_LABELS = {
    Purpose.GENERAL_CHAT: "General Chat",
    Purpose.AGENT: "Agent",
    Purpose.DOCUMENT_ANALYSIS: "Document Analysis",
    Purpose.CANDIDATE_ANALYSIS: "Candidate Analysis",
    Purpose.JOB_MATCHING: "Job Matching",
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
