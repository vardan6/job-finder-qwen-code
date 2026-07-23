import asyncio
import json
import time
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from backend.ai_capabilities import Purpose
from backend.ai_session_store import get_ai_session_store
from backend.ai_config_store import load_ai_config
from backend.database import get_db
from backend.models.candidate import Candidate
from backend.models.document import CandidateDocument
from backend.routes.ai_sessions import _normalize_session_mode
from backend.services.ai_routing import resolve_chat_model_selection


router = APIRouter(tags=["AI Chat"])

# Setup templates
templates_path = Path(__file__).parent.parent.parent / "frontend" / "templates"
templates = Jinja2Templates(directory=str(templates_path))


def _format_llm_runtime_error(exc: Exception) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    lowered = message.lower()
    if "subscription" in lowered or "upgrade" in lowered:
        return (
            "The selected provider responded, but this model is not available for the configured "
            "account or subscription. Choose another configured model or update the provider access."
        )
    if "api_key" in lowered or "unauthorized" in lowered or "authentication" in lowered:
        return (
            "The selected provider credentials were rejected. Check the configured secret or "
            "environment variable on the LLM Settings page."
        )
    if "connection" in lowered or "refused" in lowered:
        return (
            "Could not connect to the selected provider endpoint. Check the base URL and verify "
            "that the provider is reachable."
        )
    return f"Error: {message}"


def _serialize_conversation(session: dict) -> list[dict[str, str]]:
    return [
        {"role": str(message.get("role", "")), "content": str(message.get("content", ""))}
        for message in session.get("messages", [])
        if message.get("role") and message.get("content")
    ]


def _extract_stream_text(chunk) -> str:
    if chunk is None:
        return ""

    if isinstance(chunk, dict):
        choices = chunk.get("choices") or []
        if not choices:
            return str(chunk.get("text") or "")
        delta = choices[0].get("delta") or {}
        message = choices[0].get("message") or {}
        return str(delta.get("content") or message.get("content") or choices[0].get("text") or "")

    choices = getattr(chunk, "choices", None) or []
    if choices:
        choice = choices[0]
        delta = getattr(choice, "delta", None)
        if delta and getattr(delta, "content", None):
            return str(delta.content)
        message = getattr(choice, "message", None)
        if message and getattr(message, "content", None):
            return str(message.content)
        if getattr(choice, "text", None):
            return str(choice.text)

    return str(getattr(chunk, "text", "") or "")


def _supports_stream_usage(provider) -> bool:
    provider_name = str(getattr(provider, "name", "") or "").strip().lower()
    return provider_name in {"openai", "openai_compatible", "openrouter", "groq", "nvidia_nim", "nvidia"}


def _coerce_mapping(value) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        return dumped if isinstance(dumped, dict) else {}
    if hasattr(value, "dict"):
        dumped = value.dict()
        return dumped if isinstance(dumped, dict) else {}
    return {}


def _extract_usage_metadata(payload) -> dict[str, object]:
    if payload is None:
        return {}
    if isinstance(payload, dict):
        usage = payload.get("usage_metadata") or payload.get("usage") or {}
        return usage if isinstance(usage, dict) else {}

    usage_metadata = getattr(payload, "usage_metadata", None)
    usage = getattr(payload, "usage", None)
    return _coerce_mapping(usage_metadata) or _coerce_mapping(usage)


def _extract_response_metadata(payload) -> dict[str, object]:
    if payload is None:
        return {}
    if isinstance(payload, dict):
        response_metadata = payload.get("response_metadata") or {}
        if isinstance(response_metadata, dict) and response_metadata:
            return response_metadata
        return {
            key: value
            for key, value in payload.items()
            if key in {"prompt_eval_count", "eval_count", "eval_duration", "finish_reason", "stop_reason"}
        }

    response_metadata = getattr(payload, "response_metadata", None)
    meta = _coerce_mapping(response_metadata)
    if meta:
        return meta
    return {}


def _configured_provider_snapshot(provider_config_id: str) -> dict[str, str]:
    clean_id = str(provider_config_id or "").strip()
    if not clean_id:
        return {}

    config = load_ai_config()
    for provider_cfg in config.llm_providers:
        if not isinstance(provider_cfg, dict):
            continue
        if str(provider_cfg.get("id", "")).strip() != clean_id:
            continue
        provider_type = str(provider_cfg.get("provider_type", "")).strip()
        model_name = str(provider_cfg.get("model_id", "")).strip()
        display_name = str(provider_cfg.get("display_name", "")).strip() or provider_type.title()
        return {
            "id": clean_id,
            "display_name": display_name,
            "model_name": model_name,
        }
    return {}


def _selection_meta(selection, requested_provider_config_id: str, resolved_provider_config_id: str) -> dict[str, object]:
    requested_id = str(requested_provider_config_id or "").strip()
    resolved_id = str(resolved_provider_config_id or "").strip()
    requested_snapshot = _configured_provider_snapshot(requested_id)
    resolved_snapshot = _configured_provider_snapshot(resolved_id)
    fallback_used = bool(
        requested_id
        and resolved_id
        and requested_id != resolved_id
        and getattr(selection, "source", "") == "routing_fallback_from_explicit_provider"
    )
    return {
        "selection_source": str(getattr(selection, "source", "") or ""),
        "requested_provider_config_id": requested_id,
        "requested_provider_name": requested_snapshot.get("display_name", ""),
        "requested_model_name": requested_snapshot.get("model_name", ""),
        "resolved_provider_config_id": resolved_id,
        "resolved_provider_name": resolved_snapshot.get("display_name", ""),
        "resolved_model_name": resolved_snapshot.get("model_name", ""),
        "fallback_used": fallback_used,
    }


def _resolve_session_routing(
    db: Session,
    *,
    mode: str,
    model_id: int | None,
    selected_provider_config_id: str,
) -> tuple:
    """Resolve a chat request's session mode, routing purpose, and model selection.

    Shared by /api/chat and /api/chat/stream so mode-to-purpose mapping and
    its error handling can't drift between the two endpoints.
    """
    session_mode = _normalize_session_mode(mode)
    routing_purpose = Purpose.AGENT if session_mode == "agent" else Purpose.GENERAL_CHAT
    try:
        selection = resolve_chat_model_selection(
            db,
            purpose=routing_purpose,
            model_id=model_id,
            configured_provider_id=selected_provider_config_id.strip() or None,
        )
    except ValueError as exc:
        message = str(exc)
        if message == "Model not found":
            raise HTTPException(status_code=404, detail=message)
        if message == "Model has no provider configured":
            raise HTTPException(status_code=400, detail=message)
        raise HTTPException(status_code=400, detail=message)
    return session_mode, selection


def _usage_stat_number(usage: dict[str, object], *keys: str) -> int | None:
    for key in keys:
        value = usage.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _summarize_usage(usage_metadata: dict[str, object], response_metadata: dict[str, object]) -> dict[str, int] | None:
    prompt_tokens = _usage_stat_number(usage_metadata, "prompt_tokens", "input_tokens")
    if prompt_tokens is None:
        input_details = usage_metadata.get("input_token_details")
        if isinstance(input_details, dict):
            prompt_tokens = _usage_stat_number(input_details, "total_tokens")

    completion_tokens = _usage_stat_number(usage_metadata, "completion_tokens", "output_tokens")
    if completion_tokens is None:
        output_details = usage_metadata.get("output_token_details")
        if isinstance(output_details, dict):
            completion_tokens = _usage_stat_number(output_details, "total_tokens")

    total_tokens = _usage_stat_number(usage_metadata, "total_tokens")

    if prompt_tokens is None:
        prompt_tokens = _usage_stat_number(response_metadata, "prompt_eval_count")
    if completion_tokens is None:
        completion_tokens = _usage_stat_number(response_metadata, "eval_count")
    if total_tokens is None and prompt_tokens is not None and completion_tokens is not None:
        total_tokens = prompt_tokens + completion_tokens

    if prompt_tokens is None and completion_tokens is None and total_tokens is None:
        return None

    summary: dict[str, int] = {}
    if prompt_tokens is not None:
        summary["prompt_tokens"] = prompt_tokens
    if completion_tokens is not None:
        summary["completion_tokens"] = completion_tokens
    if total_tokens is not None:
        summary["total_tokens"] = total_tokens
    return summary


def _session_payload(session: dict) -> dict:
    meta = session.get("meta", {})
    return {
        "id": session["id"],
        "title": session["title"],
        "provider_id": session["provider_id"],
        "mode": session["mode"],
        "source_controls": session.get("source_controls", {}),
        "attached_candidate_id": meta.get("attached_candidate_id"),
        "attached_candidate_name": meta.get("attached_candidate_name", ""),
        "meta": meta,
    }


def _build_diagnostics_payload(session: dict, session_mode: str) -> dict:
    source_controls = session.get("source_controls") if isinstance(session, dict) else {}
    if not isinstance(source_controls, dict):
        source_controls = {}

    enabled_sources = [key for key, value in source_controls.items() if bool(value)]
    candidate_sources_enabled = any(
        source_controls.get(key)
        for key in (
            "candidate_profile",
            "candidate_job_titles",
            "candidate_skills",
            "candidate_documents",
            "job_preferences",
        )
    )
    return {
        "run_mode": session_mode,
        "enabled_source_keys": enabled_sources,
        "retrieval": {
            "candidate_context_enabled": candidate_sources_enabled,
            "source_count": len(enabled_sources),
        },
    }


async def _close_stream_if_possible(stream) -> None:
    close_method = getattr(stream, "aclose", None)
    if close_method is None:
        return
    result = close_method()
    if asyncio.iscoroutine(result):
        await result


def _prepare_messages_from_history(
    session_store,
    session: dict,
    browser_history: str,
    message: str,
    db: Session,
) -> list[dict[str, str]]:
    persisted_session = session_store.get_session(session["id"]) or session
    persisted_history = _serialize_conversation(persisted_session)

    try:
        parsed_browser_history = json.loads(browser_history)
    except (json.JSONDecodeError, TypeError):
        parsed_browser_history = []

    if persisted_history:
        messages = persisted_history[-10:]
    else:
        messages = parsed_browser_history[-10:] if isinstance(parsed_browser_history, list) else []
    system_context = _build_session_system_context(db, persisted_session)
    if system_context:
        messages = [{"role": "system", "content": system_context}, *messages]
    messages.append({"role": "user", "content": message})
    return messages


def _session_candidate_id(session: dict[str, object]) -> int | None:
    meta = session.get("meta") if isinstance(session, dict) else None
    if not isinstance(meta, dict):
        return None
    candidate_id = meta.get("attached_candidate_id")
    try:
        return int(candidate_id) if candidate_id is not None else None
    except (TypeError, ValueError):
        return None


def _candidate_profile_lines(candidate: Candidate) -> list[str]:
    lines = [f"Name: {candidate.name}"]
    if candidate.current_role:
        lines.append(f"Current role: {candidate.current_role}")
    if candidate.location:
        lines.append(f"Location: {candidate.location}")
    if candidate.timezone:
        lines.append(f"Timezone: {candidate.timezone}")
    if candidate.experience_years is not None:
        lines.append(f"Experience years: {candidate.experience_years}")
    if candidate.email:
        lines.append(f"Email: {candidate.email}")
    return lines


def _candidate_document_lines(documents: list[CandidateDocument]) -> list[str]:
    lines: list[str] = []
    for document in documents[:5]:
        detail = document.document_type or "document"
        if document.parse_status and document.parse_status != "pending":
            detail = f"{detail}; parse={document.parse_status}"
        lines.append(f"- {document.filename} ({detail})")
    return lines


def _build_session_system_context(db: Session, session: dict[str, object]) -> str:
    candidate_id = _session_candidate_id(session)
    source_controls = session.get("source_controls") if isinstance(session, dict) else None
    if not candidate_id or not isinstance(source_controls, dict):
        return ""

    candidate_source_enabled = any(
        bool(source_controls.get(key))
        for key in (
            "candidate_profile",
            "candidate_job_titles",
            "candidate_skills",
            "candidate_documents",
            "job_preferences",
        )
    )
    if not candidate_source_enabled:
        return ""

    candidate = db.query(Candidate).options(
        joinedload(Candidate.job_titles),
        joinedload(Candidate.skills),
        joinedload(Candidate.documents),
        joinedload(Candidate.preferences),
    ).filter(
        Candidate.id == candidate_id,
        Candidate.is_active == True,
    ).first()
    if candidate is None:
        return ""

    blocks = [
        "Use the following saved job-finder session context when it is relevant to the user's request.",
        f"Attached candidate ID: {candidate.id}",
    ]

    if source_controls.get("candidate_profile"):
        blocks.extend(["Candidate profile:", *_candidate_profile_lines(candidate)])

    if source_controls.get("candidate_job_titles"):
        titles = candidate.active_titles()
        if titles:
            blocks.extend(["Candidate job titles:", *[f"- {title}" for title in titles[:10]]])

    if source_controls.get("candidate_skills"):
        skills = candidate.active_skill_names()
        if skills:
            blocks.extend(["Candidate skills:", *[f"- {skill}" for skill in skills[:20]]])

    if source_controls.get("candidate_documents"):
        active_documents = [
            document for document in candidate.documents if document.is_active and document.filename
        ]
        if active_documents:
            blocks.extend(["Candidate documents:", *_candidate_document_lines(active_documents)])

    if source_controls.get("job_preferences") and candidate.preferences:
        experience_levels = []
        try:
            experience_levels = json.loads(candidate.preferences.experience_levels or "[]")
        except (json.JSONDecodeError, TypeError):
            experience_levels = []
        blocks.extend(
            [
                "Job preferences:",
                f"- Remote only: {'yes' if candidate.preferences.remote_only else 'no'}",
                f"- Minimum score: {candidate.preferences.min_score}",
                f"- Minimum AI remote score: {candidate.preferences.min_ai_remote_score}",
            ]
        )
        if experience_levels:
            blocks.append(f"- Experience levels: {', '.join(str(level) for level in experience_levels)}")

    return "\n".join(blocks)


def _get_or_create_session(
    session_store,
    session_id: str,
    provider,
    model,
    configured_provider_id: str,
    mode: str,
    initial_title: str = "",
) -> dict:
    clean_session_id = session_id.strip()
    session = session_store.get_session(clean_session_id) if clean_session_id else None
    if clean_session_id and session is None:
        raise HTTPException(status_code=404, detail="AI session not found")
    if session is None:
        session = session_store.create_session(
            title=initial_title or "New chat",
            provider_id=configured_provider_id or str(getattr(provider, "id", "")),
            mode=mode,
            meta={
                "selected_model_id": getattr(model, "id", ""),
                "selected_model_name": getattr(model, "display_name", "") or getattr(model, "model_name", ""),
                "selected_provider_name": getattr(provider, "display_name", "") or getattr(provider, "name", ""),
                "selected_provider_config_id": configured_provider_id,
            },
        )

    session_store.update_session(
        session["id"],
        provider_id=configured_provider_id or str(getattr(provider, "id", "")),
        mode=mode,
        meta={
            "selected_model_id": getattr(model, "id", ""),
            "selected_model_name": getattr(model, "display_name", "") or getattr(model, "model_name", ""),
            "selected_provider_name": getattr(provider, "display_name", "") or getattr(provider, "name", ""),
            "selected_provider_config_id": configured_provider_id,
        },
    )
    return session_store.get_session(session["id"]) or session


def _configured_chat_models() -> tuple[list[dict[str, str]], str]:
    config = load_ai_config()
    routing = config.model_routing if isinstance(config.model_routing, dict) else {}
    general_chat_rule = routing.get("general_chat", {}) if isinstance(routing.get("general_chat", {}), dict) else {}
    default_provider_config_id = str(general_chat_rule.get("primary_provider_id", "")).strip()
    options: list[dict[str, str]] = []

    for provider_cfg in config.llm_providers:
        if not isinstance(provider_cfg, dict):
            continue
        provider_config_id = str(provider_cfg.get("id", "")).strip()
        if not provider_config_id or not provider_cfg.get("enabled", True):
            continue
        provider_type = str(provider_cfg.get("provider_type", "")).strip().lower()
        model_name = str(provider_cfg.get("model_id", "")).strip()
        display_name = str(provider_cfg.get("display_name", "")).strip() or provider_type.title()
        if not provider_type or not model_name:
            continue

        options.append(
            {
                "provider_config_id": provider_config_id,
                "provider_display": display_name,
                "model_display": model_name,
            }
        )
    return options, default_provider_config_id


@router.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request, db: Session = Depends(get_db)):
    """AI Chat page"""
    candidates = db.query(Candidate).filter(Candidate.is_active == True).order_by(Candidate.name.asc()).all()
    chat_models, default_provider_config_id = _configured_chat_models()

    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request,
            "chat_models": chat_models,
            "candidates": candidates,
            "default_provider_config_id": default_provider_config_id,
        }
    )


@router.post("/api/chat")
async def chat(
    model_id: int | None = Form(default=None),
    selected_provider_config_id: str = Form(default=""),
    mode: str = Form(default="general_chat"),
    message: str = Form(...),
    session_id: str = Form(default=""),
    conversation_history: str = Form(default="[]"),
    db: Session = Depends(get_db)
):
    """Send a message to the AI and get a response (non-blocking)"""
    try:
        start_time = time.time()

        session_mode, selection = _resolve_session_routing(
            db,
            mode=mode,
            model_id=model_id,
            selected_provider_config_id=selected_provider_config_id,
        )
        model = selection.model
        provider = selection.provider
        requested_provider_config_id = selected_provider_config_id.strip()
        resolved_provider_config_id = selection.configured_provider_id or requested_provider_config_id
        selection_meta = _selection_meta(selection, requested_provider_config_id, resolved_provider_config_id)

        session_store = get_ai_session_store()
        session = _get_or_create_session(
            session_store,
            session_id,
            provider,
            model,
            resolved_provider_config_id,
            session_mode,
        )
        messages = _prepare_messages_from_history(session_store, session, conversation_history, message, db)

        session_store.add_message(session["id"], role="user", content=message)
        session_store.maybe_auto_title(session["id"], message)

        # Build completion kwargs using the shared helper
        from backend.services.llm_service import _async_completion_response, _build_completion_kwargs
        kwargs = _build_completion_kwargs(provider, model, messages)

        from backend.config import LLM_CHAT_TIMEOUT_SECONDS
        try:
            completion_response = await _async_completion_response(LLM_CHAT_TIMEOUT_SECONDS, **kwargs)
        except asyncio.TimeoutError:
            return JSONResponse(
                status_code=504,
                content={
                    "success": False,
                    "message": (
                        f"LLM did not respond within {LLM_CHAT_TIMEOUT_SECONDS}s. "
                        "Check that your provider is running and try again."
                    )
                }
            )

        ai_message = ""
        choices = getattr(completion_response, "choices", None) or []
        if choices:
            message_obj = getattr(choices[0], "message", None)
            ai_message = str(getattr(message_obj, "content", "") or "")

        if not ai_message:
            raise HTTPException(status_code=500, detail="Empty response from LLM")

        elapsed_ms = int((time.time() - start_time) * 1000)
        usage_metadata = _extract_usage_metadata(completion_response)
        response_metadata = _extract_response_metadata(completion_response)
        usage_summary = _summarize_usage(usage_metadata, response_metadata) or {}
        response_meta = {
            "provider": getattr(provider, "display_name", "") or getattr(provider, "name", ""),
            "model": getattr(model, "display_name", "") or getattr(model, "model_name", ""),
            "time_ms": elapsed_ms,
            "tokens_used": usage_summary.get("total_tokens"),
            "usage_metadata": usage_metadata,
            "response_metadata": response_metadata,
            **selection_meta,
        }
        session_store.add_message(
            session["id"],
            role="assistant",
            content=ai_message,
            model_id=str(getattr(model, "id", "")),
            provider_id=resolved_provider_config_id or str(getattr(provider, "id", "")),
            latency_ms=elapsed_ms,
            meta=response_meta,
        )
        persisted_session = session_store.get_session(session["id"]) or session
        conversation = _serialize_conversation(persisted_session)

        return {
            "success": True,
            "message": ai_message,
            "conversation": conversation,
            "session_id": session["id"],
            "session": _session_payload(persisted_session),
            "meta": response_meta,
        }

    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": _format_llm_runtime_error(e)}
        )


@router.post("/api/chat/clear")
async def clear_conversation():
    """Clear conversation history"""
    return {"success": True, "message": "Conversation cleared"}


@router.post("/api/chat/stream")
async def chat_stream(
    request: Request,
    model_id: int | None = Form(default=None),
    selected_provider_config_id: str = Form(default=""),
    mode: str = Form(default="general_chat"),
    message: str = Form(...),
    session_id: str = Form(default=""),
    conversation_history: str = Form(default="[]"),
    db: Session = Depends(get_db)
):
    """Send a message to the AI and stream the response while persisting the final turn."""
    start_time = time.time()

    session_mode, selection = _resolve_session_routing(
        db,
        mode=mode,
        model_id=model_id,
        selected_provider_config_id=selected_provider_config_id,
    )
    model = selection.model
    provider = selection.provider
    requested_provider_config_id = selected_provider_config_id.strip()
    resolved_provider_config_id = selection.configured_provider_id or requested_provider_config_id
    selection_meta = _selection_meta(selection, requested_provider_config_id, resolved_provider_config_id)

    session_store = get_ai_session_store()
    session = _get_or_create_session(
        session_store,
        session_id,
        provider,
        model,
        resolved_provider_config_id,
        session_mode,
        message,
    )
    created_new_session = not session_id.strip()
    messages = _prepare_messages_from_history(session_store, session, conversation_history, message, db)

    from backend.services.llm_service import _build_completion_kwargs
    kwargs = _build_completion_kwargs(provider, model, messages)
    kwargs["stream"] = True
    if _supports_stream_usage(provider):
        stream_options = kwargs.get("stream_options")
        if not isinstance(stream_options, dict):
            stream_options = {}
        stream_options.setdefault("include_usage", True)
        kwargs["stream_options"] = stream_options

    from backend.config import LLM_CHAT_TIMEOUT_SECONDS

    async def generate():
        parts: list[str] = []
        stream_usage_metadata: dict[str, object] = {}
        stream_response_metadata: dict[str, object] = {}
        stream = None
        user_message_persisted = False
        client_disconnected = False

        def persist_user_message() -> None:
            nonlocal user_message_persisted
            if user_message_persisted:
                return
            session_store.add_message(session["id"], role="user", content=message)
            session_store.maybe_auto_title(session["id"], message)
            user_message_persisted = True

        try:
            yield f"data: {json.dumps({'type': 'session', 'session_id': session['id'], 'session': _session_payload(session_store.get_session(session['id'], include_messages=False) or session)})}\n\n"

            if session_mode == "agent":
                yield f"data: {json.dumps({'type': 'trace', 'stage': 'routing', 'message': f'Run mode {session_mode} selected', 'status': 'ok'})}\n\n"
                yield f"data: {json.dumps({'type': 'tool_activity', 'tool': 'session_context', 'status': 'started', 'message': 'Collecting candidate/session context'})}\n\n"

            if session_mode == "agent" and message.strip().lower().startswith("/plan"):
                persist_user_message()
                yield f"data: {json.dumps({'type': 'interaction_required', 'interaction': {'kind': 'clarification', 'title': 'Plan clarification needed', 'prompt': 'Confirm scope before executing the plan.', 'options': ['Use current session context', 'Limit to this message only']}})}\n\n"
                return

            from litellm import acompletion

            stream = await asyncio.wait_for(
                acompletion(**kwargs),
                timeout=LLM_CHAT_TIMEOUT_SECONDS,
            )

            while True:
                if await request.is_disconnected():
                    client_disconnected = True
                    break
                try:
                    chunk = await asyncio.wait_for(stream.__anext__(), timeout=LLM_CHAT_TIMEOUT_SECONDS)
                except StopAsyncIteration:
                    break

                chunk_usage_metadata = _extract_usage_metadata(chunk)
                if chunk_usage_metadata:
                    stream_usage_metadata.update(chunk_usage_metadata)
                chunk_response_metadata = _extract_response_metadata(chunk)
                if chunk_response_metadata:
                    stream_response_metadata.update(chunk_response_metadata)
                text = _extract_stream_text(chunk)
                if not text:
                    continue
                parts.append(text)
                yield f"data: {json.dumps({'type': 'chunk', 'delta': text})}\n\n"

                if session_mode == "agent":
                    yield f"data: {json.dumps({'type': 'tool_activity', 'tool': 'llm_stream', 'status': 'running', 'message': f'Received {len(parts)} response chunk(s)'})}\n\n"

            if client_disconnected:
                return

            ai_message = "".join(parts).strip()
            if not ai_message:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Empty response from LLM'})}\n\n"
                return

            elapsed_ms = int((time.time() - start_time) * 1000)
            usage_summary = _summarize_usage(stream_usage_metadata, stream_response_metadata) or {}
            response_meta = {
                "provider": getattr(provider, "display_name", "") or getattr(provider, "name", ""),
                "model": getattr(model, "display_name", "") or getattr(model, "model_name", ""),
                "time_ms": elapsed_ms,
                "tokens_used": usage_summary.get("total_tokens"),
                "usage_metadata": stream_usage_metadata,
                "response_metadata": stream_response_metadata,
                **selection_meta,
            }
            persist_user_message()
            session_store.add_message(
                session["id"],
                role="assistant",
                content=ai_message,
                model_id=str(getattr(model, "id", "")),
                provider_id=resolved_provider_config_id or str(getattr(provider, "id", "")),
                latency_ms=elapsed_ms,
                meta=response_meta,
            )
            persisted_session = session_store.get_session(session["id"]) or session
            diagnostics = _build_diagnostics_payload(persisted_session, session_mode)
            yield f"data: {json.dumps({'type': 'done', 'message': ai_message, 'conversation': _serialize_conversation(persisted_session), 'session_id': session['id'], 'session': _session_payload(persisted_session), 'meta': response_meta, 'diagnostics': diagnostics})}\n\n"
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            yield f"data: {json.dumps({'type': 'error', 'message': f'LLM did not respond within {LLM_CHAT_TIMEOUT_SECONDS}s. Check that your provider is running and try again.'})}\n\n"
        except HTTPException:
            raise
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': _format_llm_runtime_error(exc)})}\n\n"
        finally:
            if stream is not None:
                await _close_stream_if_possible(stream)
            if not user_message_persisted and created_new_session:
                persisted_session = session_store.get_session(session["id"])
                if persisted_session and not persisted_session.get("messages"):
                    session_store.purge_session(session["id"])

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
