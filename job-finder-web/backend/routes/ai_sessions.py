from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.ai_capabilities import SESSION_MODES
from backend.ai_session_store import get_ai_session_store
from backend.database import get_db
from backend.models.candidate import Candidate

router = APIRouter()


def _session_or_404(session_id: str) -> dict[str, Any]:
    session = get_ai_session_store().get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="AI session not found")
    return session


def _normalize_session_mode(value: Any) -> str:
    mode = str(value or "general_chat").strip().lower()
    if not mode:
        mode = "general_chat"
    if mode not in SESSION_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"mode must be one of: {', '.join(SESSION_MODES)}",
        )
    return mode


def _candidate_meta_update(payload: dict[str, Any], db: Session) -> dict[str, Any] | None:
    if "attached_candidate_id" not in payload:
        return None

    candidate_id = payload.get("attached_candidate_id")
    if candidate_id in ("", None):
        return {
            "attached_candidate_id": None,
            "attached_candidate_name": "",
        }

    try:
        candidate_id = int(candidate_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="attached_candidate_id must be an integer or null") from exc

    candidate = db.query(Candidate).filter(
        Candidate.id == candidate_id,
        Candidate.is_active == True,
    ).first()
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")

    return {
        "attached_candidate_id": candidate.id,
        "attached_candidate_name": candidate.name,
    }


@router.get("/api/ai/sessions")
async def list_ai_sessions(
    limit: int = Query(default=100, ge=1, le=500),
    include_archived: bool = False,
    archived_only: bool = False,
) -> dict[str, Any]:
    sessions = get_ai_session_store().list_sessions(
        limit=limit,
        include_archived=include_archived,
        archived_only=archived_only,
    )
    return {"sessions": sessions}


@router.post("/api/ai/sessions")
async def create_ai_session(
    payload: dict[str, Any] | None = None,
    db: Session = Depends(get_db),
) -> JSONResponse:
    body = payload if isinstance(payload, dict) else {}
    meta = body.get("meta") if isinstance(body.get("meta"), dict) else {}
    candidate_meta = _candidate_meta_update(body, db)
    if candidate_meta is not None:
        meta = {**meta, **candidate_meta}
    session = get_ai_session_store().create_session(
        title=str(body.get("title", "New chat")),
        mode=_normalize_session_mode(body.get("mode", "general_chat")),
        provider_id=str(body.get("provider_id", "")),
        source_controls=body.get("source_controls"),
        meta=meta,
    )
    return JSONResponse({"ok": True, "session": session}, status_code=201)


@router.get("/api/ai/sessions/{session_id}")
async def get_ai_session(session_id: str) -> dict[str, Any]:
    return {"session": _session_or_404(session_id)}


@router.patch("/api/ai/sessions/{session_id}")
async def update_ai_session(
    session_id: str,
    payload: dict[str, Any],
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="session payload must be an object")
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    candidate_meta = _candidate_meta_update(payload, db)
    if candidate_meta is not None:
        meta = {**meta, **candidate_meta}
    session = get_ai_session_store().update_session(
        session_id,
        title=payload.get("title"),
        mode=_normalize_session_mode(payload["mode"]) if "mode" in payload else None,
        provider_id=payload.get("provider_id"),
        source_controls=payload.get("source_controls") if "source_controls" in payload else None,
        meta=meta,
    )
    if session is None:
        raise HTTPException(status_code=404, detail="AI session not found")
    return {"ok": True, "session": session}


@router.post("/api/ai/sessions/{session_id}/archive")
async def archive_ai_session(session_id: str) -> dict[str, Any]:
    if not get_ai_session_store().archive_session(session_id):
        raise HTTPException(status_code=404, detail="AI session not found")
    return {"ok": True, "session": _session_or_404(session_id)}


@router.post("/api/ai/sessions/{session_id}/restore")
async def restore_ai_session(session_id: str) -> dict[str, Any]:
    if not get_ai_session_store().restore_session(session_id):
        raise HTTPException(status_code=404, detail="AI session not found")
    return {"ok": True, "session": _session_or_404(session_id)}


@router.delete("/api/ai/sessions/{session_id}")
async def purge_ai_session(session_id: str) -> dict[str, Any]:
    if not get_ai_session_store().purge_session(session_id):
        raise HTTPException(status_code=404, detail="AI session not found")
    return {"ok": True}


@router.get("/api/ai/sessions/{session_id}/messages")
async def list_ai_session_messages(
    session_id: str,
    limit: int = Query(default=20, ge=1, le=200),
    before_message_id: str = "",
    role: str = "",
) -> dict[str, Any]:
    _session_or_404(session_id)
    messages = get_ai_session_store().list_session_messages(
        session_id,
        limit=limit,
        before_message_id=before_message_id,
        role=role,
    )
    return {"messages": messages}


@router.get("/api/ai/messages/search")
async def search_ai_messages(
    query: str,
    limit: int = Query(default=20, ge=1, le=200),
    session_id: str = "",
    include_archived: bool = False,
    role: str = "",
) -> dict[str, Any]:
    matches = get_ai_session_store().search_messages(
        query,
        limit=limit,
        session_id=session_id,
        include_archived=include_archived,
        role=role,
    )
    return {"matches": matches}
