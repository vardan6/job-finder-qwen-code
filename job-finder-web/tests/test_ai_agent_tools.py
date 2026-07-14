from __future__ import annotations

import pytest

from backend.ai_agent import AGENT_TOOL_REGISTRY, get_agent_tool_definition
from backend.ai_agent.schemas import ToolPermission, ToolValidationError
from backend.models.candidate import Candidate
from backend.models.supporting import CandidateSkill


def test_agent_tool_registry_exposes_typed_read_only_tools() -> None:
    by_name = {tool.name: tool for tool in AGENT_TOOL_REGISTRY}

    assert set(by_name) == {"list_data_surfaces", "candidate_skills_lookup"}
    assert by_name["list_data_surfaces"].permission == ToolPermission.READ
    assert by_name["candidate_skills_lookup"].permission == ToolPermission.READ
    assert by_name["candidate_skills_lookup"].required_scopes == frozenset(
        {"candidate:read", "candidate_skills:read"}
    )
    assert by_name["candidate_skills_lookup"].to_model_tool()["function"]["parameters"]["type"] == "object"


def test_candidate_skills_args_are_schema_validated() -> None:
    tool = get_agent_tool_definition("candidate_skills_lookup")
    assert tool is not None

    assert tool.validate_args({"candidate_id": 12}) == {"candidate_id": 12}

    with pytest.raises(ToolValidationError, match="candidate_id is required"):
        tool.validate_args({})

    with pytest.raises(ToolValidationError, match="candidate_id has invalid type"):
        tool.validate_args({"candidate_id": "12"})

    with pytest.raises(ToolValidationError, match="unexpected argument"):
        tool.validate_args({"candidate_id": 12, "include_inactive": True})


def test_list_data_surfaces_reports_compact_manifest() -> None:
    tool = get_agent_tool_definition("list_data_surfaces")
    assert tool is not None
    args = tool.validate_args(
        {
            "attached_candidate_id": 7,
            "current_session_id": "session-1",
            "source_controls": {
                "candidate_skills": True,
                "candidate_documents": False,
                "workspace_files": True,
            },
        }
    )

    result = tool.handler(args, db=None)

    assert result["candidate"]["attached_candidate_id"] == 7
    assert "skills" in result["candidate"]["available"]
    assert "documents" not in result["candidate"]["available"]
    assert result["chat_history"]["current_session_id"] == "session-1"
    assert result["workspace_files"]["read_available"] is True
    assert result["workspace_files"]["write_requires_approval"] is True


def test_candidate_skills_tool_reuses_existing_handler(db) -> None:
    candidate = Candidate(name="Casey", email="casey@example.com", current_role="Backend Engineer")
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    db.add(CandidateSkill(candidate_id=candidate.id, skill_name="Python", category="required", years_experience=8))
    db.commit()

    tool = get_agent_tool_definition("candidate_skills_lookup")
    assert tool is not None
    args = tool.validate_args({"candidate_id": candidate.id})
    result = tool.handler(args, db)

    assert result["candidate_id"] == candidate.id
    assert result["skills"][0]["skill_name"] == "Python"
