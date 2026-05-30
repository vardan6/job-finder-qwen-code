"""
AI Chat Routes - Simple chat interface with LLM.
"""
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path
from typing import Optional
import asyncio
import json
import time

from backend.database import get_db
from backend.models.document import LLMFunctionMapping
from backend.models.llm_provider import LLMProvider, LLMModel


router = APIRouter(tags=["AI Chat"])

# Setup templates
templates_path = Path(__file__).parent.parent.parent / "frontend" / "templates"
templates = Jinja2Templates(directory=str(templates_path))


@router.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request, db: Session = Depends(get_db)):
    """AI Chat page"""
    providers = db.query(LLMProvider).filter(LLMProvider.is_active == True).all()

    chat_mapping = db.query(LLMFunctionMapping).filter(
        LLMFunctionMapping.function_name == "ai_chat",
        LLMFunctionMapping.is_active == True
    ).first()

    default_model_id = None
    if chat_mapping and chat_mapping.model_id:
        default_model_id = chat_mapping.model_id

    for provider in providers:
        db.refresh(provider)

    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request,
            "providers": providers,
            "default_model_id": default_model_id,
        }
    )


@router.post("/api/chat")
async def chat(
    model_id: int = Form(...),
    message: str = Form(...),
    conversation_history: str = Form(default="[]"),
    db: Session = Depends(get_db)
):
    """Send a message to the AI and get a response (non-blocking)"""
    try:
        start_time = time.time()

        model = db.query(LLMModel).filter(LLMModel.id == model_id).first()
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")

        try:
            history = json.loads(conversation_history)
        except (json.JSONDecodeError, TypeError):
            history = []

        messages = history[-10:]
        messages.append({"role": "user", "content": message})

        provider = model.provider
        if not provider:
            raise HTTPException(status_code=400, detail="Model has no provider configured")

        # Build completion kwargs using the shared helper
        from backend.services.llm_service import _async_completion, _build_completion_kwargs
        kwargs = _build_completion_kwargs(provider, model, messages)

        from backend.config import LLM_CHAT_TIMEOUT_SECONDS
        try:
            ai_message = await _async_completion(LLM_CHAT_TIMEOUT_SECONDS, **kwargs)
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

        if not ai_message:
            raise HTTPException(status_code=500, detail="Empty response from LLM")

        elapsed_ms = int((time.time() - start_time) * 1000)

        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": ai_message})

        return {
            "success": True,
            "message": ai_message,
            "conversation": history,
            "meta": {
                "provider": provider.name,
                "model": model.display_name or model.model_name,
                "time_ms": elapsed_ms,
                "tokens_used": None,
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error: {str(e)}"}
        )


@router.post("/api/chat/clear")
async def clear_conversation():
    """Clear conversation history"""
    return {"success": True, "message": "Conversation cleared"}
