"""
AI Chat Routes - Simple chat interface with LLM
"""
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path
from typing import Optional, List
import json
import time

from backend.database import get_db
from backend.models.document import LLMFunctionMapping
from backend.models.llm_provider import LLMProvider, LLMModel
from backend.services.llm_service import call_llm


router = APIRouter(tags=["AI Chat"])

# Setup templates
templates_path = Path(__file__).parent.parent.parent / "frontend" / "templates"
templates = Jinja2Templates(directory=str(templates_path))


@router.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request, db: Session = Depends(get_db)):
    """AI Chat page"""
    # Get all providers with their models
    providers = db.query(LLMProvider).filter(LLMProvider.is_active == True).all()

    # Get default model for chat
    chat_mapping = db.query(LLMFunctionMapping).filter(
        LLMFunctionMapping.function_name == "ai_chat",
        LLMFunctionMapping.is_active == True
    ).first()

    default_model_id = None
    if chat_mapping and chat_mapping.model_id:
        default_model_id = chat_mapping.model_id

    # Eagerly load models for each provider
    for provider in providers:
        db.refresh(provider)  # This loads the models relationship

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
    request: Request,
    model_id: int = Form(...),
    message: str = Form(...),
    conversation_history: str = Form(default="[]"),
    db: Session = Depends(get_db)
):
    """Send a message to the AI and get a response"""
    try:
        # Get the model
        model = db.query(LLMModel).filter(LLMModel.id == model_id).first()
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")
        
        # Parse conversation history
        try:
            history = json.loads(conversation_history)
        except:
            history = []
        
        # Build messages for the LLM
        messages = history[-10:]  # Keep last 10 messages for context
        messages.append({"role": "user", "content": message})
        
        # Get provider info
        provider = model.provider
        if not provider:
            raise HTTPException(status_code=400, detail="Model has no provider configured")
        
        # Call the LLM
        from litellm import completion

        # Build model identifier with proper provider prefix
        # NVIDIA NIM requires "nvidia_nim/" prefix (not "nvidia/")
        provider_prefixes = {
            "ollama": "ollama/",
            "nvidia": "nvidia_nim/",  # LiteLLM requires nvidia_nim/ prefix
            "nvidia_nim": "nvidia_nim/",
            "openrouter": "openrouter/",
            "anthropic": "anthropic/",
            "openai": "openai/",
        }

        prefix = provider_prefixes.get(provider.name, "")

        # For Ollama, use host + model
        if provider.name == "ollama":
            model_name = f"ollama/{model.model_name}"
            api_base = provider.api_url or "http://localhost:11434"
        elif provider.name in ["nvidia", "nvidia_nim"]:
            # NVIDIA NIM: model stored as "meta/llama3-70b-instruct", prefix with "nvidia_nim/"
            model_name = f"nvidia_nim/{model.model_name}"
            api_base = None  # Use default NVIDIA NIM endpoint
        else:
            # For other providers, add prefix if not already in model name
            if not model.model_name.startswith(prefix):
                model_name = prefix + model.model_name
            else:
                model_name = model.model_name
            # Use provider API URL, but strip trailing /v1 if present (LiteLLM adds it)
            api_base = provider.api_url
            if api_base and api_base.endswith('/v1'):
                api_base = api_base[:-3]  # Remove /v1, LiteLLM will add it
        
        # Prepare completion kwargs
        kwargs = {
            "model": model_name,
            "messages": messages,
        }
        
        if api_base:
            kwargs["api_base"] = api_base
        
        # Add API key if present
        if provider.api_key_encrypted and provider.name != "ollama":
            from backend.security import decrypt_data
            api_key = decrypt_data(provider.api_key_encrypted)
            if api_key:
                kwargs["api_key"] = api_key
        
        # Call the LLM
        response = completion(**kwargs)
        
        if response and response.choices and len(response.choices) > 0:
            ai_message = response.choices[0].message.content
            
            # Update conversation history
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": ai_message})
            
            return {
                "success": True,
                "message": ai_message,
                "conversation": history
            }
        else:
            raise HTTPException(status_code=500, detail="Empty response from LLM")
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Error: {str(e)}"}
        )


@router.post("/api/chat/clear")
async def clear_conversation():
    """Clear conversation history"""
    return {"success": True, "message": "Conversation cleared"}
