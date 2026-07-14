from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.ai_session_store import default_source_controls, normalize_source_controls
from backend.ai_tool_registry import execute_tool
from backend.ai_agent.schemas import ToolDefinition, ToolPermission


def _execute_existing_tool(name: str, args: dict[str, Any], db: Session) -> dict[str, Any]:
    return execute_tool(name, args, db)


def _list_data_surfaces(args: dict[str, Any], db: Session) -> dict[str, Any]:
    attached_candidate_id = args.get("attached_candidate_id")
    source_controls = args.get("source_controls")
    controls = normalize_source_controls(source_controls) if isinstance(source_controls, dict) else default_source_controls()

    available_candidate_surfaces: list[str] = []
    if controls.get("candidate_profile"):
        available_candidate_surfaces.append("profile")
    if controls.get("candidate_job_titles"):
        available_candidate_surfaces.append("job_titles")
    if controls.get("candidate_skills"):
        available_candidate_surfaces.append("skills")
    if controls.get("candidate_documents"):
        available_candidate_surfaces.append("documents")

    return {
        "candidate": {
            "attached_candidate_id": attached_candidate_id,
            "available": available_candidate_surfaces,
        },
        "chat_history": {
            "current_session_id": args.get("current_session_id"),
            "search_available": bool(controls.get("ai_chat_history")),
        },
        "workspace_files": {
            "read_available": bool(controls.get("workspace_files")),
            "write_requires_approval": True,
        },
        "settings": {
            "redacted_provider_config_available": bool(controls.get("settings_config")),
        },
    }


LIST_DATA_SURFACES = ToolDefinition(
    name="list_data_surfaces",
    description="List compact metadata for the data surfaces available to this agent run.",
    permission=ToolPermission.READ,
    tier=0,
    required_scopes=frozenset({"manifest:read"}),
    side_effects=frozenset(),
    input_schema={
        "type": "object",
        "properties": {
            "attached_candidate_id": {"type": ["integer", "null"]},
            "current_session_id": {"type": ["string", "null"]},
            "source_controls": {"type": "object"},
        },
        "required": [],
        "additionalProperties": False,
    },
    output_schema={
        "type": "object",
        "properties": {
            "candidate": {"type": "object"},
            "chat_history": {"type": "object"},
            "workspace_files": {"type": "object"},
            "settings": {"type": "object"},
        },
        "required": ["candidate", "chat_history", "workspace_files", "settings"],
        "additionalProperties": False,
    },
    handler=_list_data_surfaces,
)


CANDIDATE_SKILLS_LOOKUP = ToolDefinition(
    name="candidate_skills_lookup",
    description="Read normalized active skill records for the attached candidate.",
    permission=ToolPermission.READ,
    tier=1,
    required_scopes=frozenset({"candidate:read", "candidate_skills:read"}),
    side_effects=frozenset(),
    input_schema={
        "type": "object",
        "properties": {
            "candidate_id": {"type": "integer", "minimum": 1},
        },
        "required": ["candidate_id"],
        "additionalProperties": False,
    },
    output_schema={
        "type": "object",
        "properties": {
            "candidate_id": {"type": "integer"},
            "skills": {"type": "array"},
        },
        "required": ["candidate_id", "skills"],
        "additionalProperties": False,
    },
    handler=lambda args, db: _execute_existing_tool("candidate_skills_lookup", args, db),
)


AGENT_TOOL_REGISTRY: tuple[ToolDefinition, ...] = (
    LIST_DATA_SURFACES,
    CANDIDATE_SKILLS_LOOKUP,
)


def get_agent_tool_definition(name: str) -> ToolDefinition | None:
    return next((tool for tool in AGENT_TOOL_REGISTRY if tool.name == name), None)
