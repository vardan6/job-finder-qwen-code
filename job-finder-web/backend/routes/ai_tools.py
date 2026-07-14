from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.ai_tool_registry import TOOL_REGISTRY, execute_tool, get_tool_definition
from backend.database import get_db

router = APIRouter()


@router.get("/api/ai/tools")
async def list_ai_tools() -> dict[str, Any]:
    return {
        "tools": list(TOOL_REGISTRY),
        "count": len(TOOL_REGISTRY),
    }


@router.post("/api/ai/tools/execute")
async def execute_ai_tool(payload: dict[str, Any], db: Session = Depends(get_db)) -> JSONResponse:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="tool payload must be an object")

    tool_name = str(payload.get("tool", "")).strip()
    if not tool_name:
        raise HTTPException(status_code=400, detail="tool is required")
    tool_definition = get_tool_definition(tool_name)
    if tool_definition is None:
        raise HTTPException(status_code=404, detail=f"Unknown tool: {tool_name}")

    args = payload.get("args", {})
    if not isinstance(args, dict):
        raise HTTPException(status_code=400, detail="args must be an object")

    # Approval handshake for write tools: caller must explicitly confirm mutation intent.
    if tool_definition.get("mode") == "write":
        approval = payload.get("approval", {})
        if not isinstance(approval, dict):
            raise HTTPException(status_code=400, detail="approval must be an object")
        if approval.get("state") != "approved":
            return JSONResponse(
                status_code=409,
                content={
                    "ok": False,
                    "tool": tool_name,
                    "approval_required": True,
                    "required": {"state": "approved"},
                },
            )

    result = execute_tool(tool_name, args, db)
    return JSONResponse({"ok": True, "tool": tool_name, "result": result})
