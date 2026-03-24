"""
LLM Provider Configuration Routes - CRUD operations for AI providers
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional, List
from pathlib import Path
import time

from backend.database import get_db
from backend.models.llm_provider import LLMProvider, LLMModel
from backend.security import encrypt_data, decrypt_data
from backend.config import OLLAMA_URL, DEFAULT_LLM_MODEL

router = APIRouter()

# Setup templates
templates_path = Path(__file__).parent.parent.parent / "frontend" / "templates"
templates = Jinja2Templates(directory=templates_path)


def get_default_provider(db: Session):
    """Get the default LLM provider from database"""
    provider = db.query(LLMProvider).filter(LLMProvider.is_global_default == True).first()
    if not provider:
        # Default to Ollama if nothing is set
        provider = db.query(LLMProvider).filter(LLMProvider.name == "ollama").first()
    return provider

# Default providers with their common models
DEFAULT_PROVIDERS = {
    "ollama": {
        "display_name": "Ollama (Local)",
        "api_url": OLLAMA_URL,
        "is_active": True,
        "models": ["llama3", "llama3.1", "mistral", "gemma", "codellama", "phi3"]
    },
    "nvidia": {
        "display_name": "NVIDIA (NIM)",
        "api_url": "https://integrate.api.nvidia.com/v1",
        "is_active": False,
        "models": [
            # Free tier models (tested & working)
            "meta/llama3-70b-instruct",
            "meta/llama3-8b-instruct",
            # Llama 3.1 series
            "meta/llama-3.1-70b-instruct",
            "meta/llama-3.1-8b-instruct",
            "meta/llama-3.1-405b-instruct",  # Requires credits
            # Qwen models (Continue.dev - tested & working)
            "qwen/qwen3-coder-480b-a35b-instruct",
            "qwen/qwen2.5-coder-32b-instruct",
            "qwen/qwen-2-7b-instruct",
            # OpenAI models via NVIDIA (Continue.dev style - use nvidia_nim/ prefix)
            "openai/gpt-oss-120b",
            # Mistral models
            "mistralai/mistral-large",
            "mistralai/mixtral-8x22b-instruct",
            "mistralai/mistral-7b-instruct",
            "mistralai/mistral-8x7b-instruct",
            # Google models
            "google/gemma-7b",
            "google/gemma-2b",
            "google/codegemma-7b",
            "google/recurrentgemma-2b",
            # NVIDIA models
            "nvidia/nemotron-4-340b-instruct",  # Requires credits
            "nvidia/nemotron-4-340b-reward",
            "nvidia/usdcode-llama3-70b-instruct",
            "nvidia/nv-rerankqa-mistral-4b-v3",
            "nvidia/nv-embedqa-e5-v5",
            "nvidia/nv-embedqa-mistral-7b-v2",
            # Microsoft Phi-3 models
            "microsoft/phi-3-mini-128k-instruct",
            "microsoft/phi-3-mini-4k-instruct",
            "microsoft/phi-3-medium-128k-instruct",
            "microsoft/phi-3-medium-4k-instruct",
            # Other models
            "deepseek-ai/deepseek-coder-6.7b-instruct",
            "snowflake/arctic",
            "upstage/solar-10.7b-instruct"
        ]
    },
    "openrouter": {
        "display_name": "OpenRouter",
        "api_url": "https://openrouter.ai/api/v1",
        "is_active": False,
        "models": ["meta-llama/llama-3-70b-instruct", "mistralai/mistral-large", "google/gemma-7b"]
    },
    "anthropic": {
        "display_name": "Anthropic (Claude)",
        "api_url": "https://api.anthropic.com",
        "is_active": False,
        "models": ["claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"]
    },
    "openai": {
        "display_name": "OpenAI (GPT)",
        "api_url": "https://api.openai.com/v1",
        "is_active": False,
        "models": ["gpt-4-turbo", "gpt-4", "gpt-3.5-turbo"]
    }
}


@router.get("/")
async def settings_index():
    """Redirect /settings to /settings/llm"""
    return RedirectResponse(url="/settings/llm")


@router.get("/llm", response_class=HTMLResponse)
async def list_llm_providers(request: Request, db: Session = Depends(get_db)):
    """List all LLM providers with their models"""
    providers = db.query(LLMProvider).all()

    # Merge with default providers
    db_provider_names = {p.name for p in providers}
    for name, default in DEFAULT_PROVIDERS.items():
        if name not in db_provider_names:
            # Create default provider
            provider = LLMProvider(
                name=name,
                api_url=default["api_url"],
                is_active=default["is_active"]
            )
            db.add(provider)
            db.commit()
            db.refresh(provider)
            
            # Add default models
            for model_name in default["models"]:
                model = LLMModel(
                    provider_id=provider.id,
                    model_name=model_name,
                    display_name=model_name,
                    is_default_for_provider=(model_name == default["models"][0]),
                    is_active=True
                )
                db.add(model)
            db.commit()
            providers.append(provider)

    # Load models for each provider
    for provider in providers:
        db.refresh(provider)  # This loads the models relationship

    # Get current default provider
    default_provider = get_default_provider(db)

    return templates.TemplateResponse("settings/llm.html", {
        "request": request,
        "providers": providers,
        "default_provider": default_provider,
        "default_model": DEFAULT_LLM_MODEL
    })


@router.post("/")
async def create_or_update_llm_provider(
    request: Request,
    name: str = Form(...),
    api_key: Optional[str] = Form(None),
    api_url: Optional[str] = Form(None),
    is_global_default: Optional[str] = Form(None),  # Checkbox comes as "on" string or None
    db: Session = Depends(get_db)
):
    """Create or update an LLM provider"""
    try:
        # Convert checkbox string to boolean
        is_default = is_global_default == "on" or is_global_default == "true" or is_global_default is True

        # Debug logging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Saving provider: {name}")
        logger.info(f"  - api_key provided: {bool(api_key and api_key.strip())}")
        logger.info(f"  - api_url: {api_url}")
        logger.info(f"  - is_global_default: {is_default}")

        provider = db.query(LLMProvider).filter(LLMProvider.name == name).first()

        if provider:
            # Update existing
            if api_key and api_key.strip():
                logger.info(f"  - Updating API key for {name}")
                provider.api_key_encrypted = encrypt_data(api_key)
            if api_url:
                provider.api_url = api_url
            provider.is_global_default = is_default
        else:
            # Create new
            if not api_key and name != "ollama":
                raise HTTPException(status_code=400, detail="API key is required for cloud providers")

            provider = LLMProvider(
                name=name,
                api_key_encrypted=encrypt_data(api_key) if api_key else None,
                api_url=api_url,
                is_global_default=is_default
            )
            db.add(provider)
            db.commit()
            db.refresh(provider)
            
            # Add default models for new provider
            if name in DEFAULT_PROVIDERS:
                for model_name in DEFAULT_PROVIDERS[name]["models"]:
                    model = LLMModel(
                        provider_id=provider.id,
                        model_name=model_name,
                        display_name=model_name,
                        is_default_for_provider=(model_name == DEFAULT_PROVIDERS[name]["models"][0]),
                        is_active=True
                    )
                    db.add(model)
                db.commit()

        # If this is set as default, unset others
        if is_default:
            db.query(LLMProvider).filter(LLMProvider.name != name).update({"is_global_default": False})

        db.commit()
        logger.info(f"Provider {name} saved successfully!")

        return RedirectResponse(url="/settings/llm?success=saved", status_code=303)

    except Exception as e:
        db.rollback()
        # Log the error for debugging
        import logging
        logging.error(f"Error saving provider {name}: {e}")
        # Redirect back with error message
        return RedirectResponse(url=f"/settings/llm?error={str(e)}", status_code=303)


@router.post("/delete")
async def delete_llm_provider(
    request: Request,
    name: str = Form(...),
    db: Session = Depends(get_db)
):
    """Delete an LLM provider (cannot delete Ollama)"""
    if name == "ollama":
        raise HTTPException(status_code=400, detail="Cannot delete Ollama (local provider)")

    provider = db.query(LLMProvider).filter(LLMProvider.name == name).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    db.delete(provider)
    db.commit()

    return RedirectResponse(url="/settings/llm?success=deleted", status_code=303)


@router.post("/set-default")
async def set_default_provider(
    request: Request,
    name: str = Form(...),
    db: Session = Depends(get_db)
):
    """Set a provider as the default (without changing other settings)"""
    try:
        # Set this provider as default
        provider = db.query(LLMProvider).filter(LLMProvider.name == name).first()
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")
        
        # Unset all others first
        db.query(LLMProvider).filter(LLMProvider.name != name).update({"is_global_default": False})
        
        # Set this one as default
        provider.is_global_default = True
        db.commit()
        
        logger.info(f"Set {name} as default provider")
        return RedirectResponse(url="/settings/llm?success=saved", status_code=303)
    except Exception as e:
        db.rollback()
        return RedirectResponse(url=f"/settings/llm?error={str(e)}", status_code=303)


@router.post("/model/add")
async def add_model(
    request: Request,
    provider_id: str = Form(...),
    model_name: str = Form(...),
    display_name: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Add a new model to a provider"""
    try:
        provider = db.query(LLMProvider).filter(LLMProvider.id == int(provider_id)).first()
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")
        
        # Check if model already exists
        existing = db.query(LLMModel).filter(
            LLMModel.provider_id == provider.id,
            LLMModel.model_name == model_name
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Model already exists for this provider")
        
        # Check if this is the first model for this provider (make it default)
        existing_models = db.query(LLMModel).filter(LLMModel.provider_id == provider.id).all()
        is_default = len(existing_models) == 0
        
        model = LLMModel(
            provider_id=provider.id,
            model_name=model_name,
            display_name=display_name or model_name,
            is_default_for_provider=is_default,
            is_active=True
        )
        db.add(model)
        db.commit()
        
        return RedirectResponse(url="/settings/llm?success=model_added", status_code=303)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        import logging
        logging.error(f"Error adding model: {e}")
        return RedirectResponse(url=f"/settings/llm?error={str(e)}", status_code=303)


@router.post("/model/remove")
async def remove_model(
    request: Request,
    model_id: str = Form(...),
    db: Session = Depends(get_db)
):
    """Remove a model from a provider"""
    try:
        model = db.query(LLMModel).filter(LLMModel.id == int(model_id)).first()
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")
        
        # Don't allow removing the last model
        provider = db.query(LLMProvider).filter(LLMProvider.id == model.provider_id).first()
        if provider:
            remaining_models = db.query(LLMModel).filter(LLMModel.provider_id == provider.id).all()
            if len(remaining_models) <= 1:
                raise HTTPException(status_code=400, detail="Cannot remove the last model from a provider")
        
        db.delete(model)
        db.commit()
        
        return RedirectResponse(url="/settings/llm?success=model_removed", status_code=303)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        import logging
        logging.error(f"Error removing model: {e}")
        return RedirectResponse(url=f"/settings/llm?error={str(e)}", status_code=303)


@router.post("/model/set_default")
async def set_model_as_default(
    request: Request,
    model_id: str = Form(...),
    db: Session = Depends(get_db)
):
    """Set a model as the default for its provider"""
    try:
        model = db.query(LLMModel).filter(LLMModel.id == int(model_id)).first()
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")
        
        # Unset all other models for this provider
        db.query(LLMModel).filter(LLMModel.provider_id == model.provider_id).update(
            {"is_default_for_provider": False}
        )
        
        # Set this model as default
        model.is_default_for_provider = True
        db.commit()
        
        return RedirectResponse(url="/settings/llm?success=default_set", status_code=303)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        import logging
        logging.error(f"Error setting default model: {e}")
        return RedirectResponse(url=f"/settings/llm?error={str(e)}", status_code=303)


@router.post("/test")
async def test_llm_provider(
    request: Request,
    model: str = Form(...),
    prompt: str = Form(default="Hello! Please respond with 'OK' if you can read this."),
    db: Session = Depends(get_db)
):
    """Test an LLM provider connection"""
    start_time = time.time()

    import logging
    logger = logging.getLogger(__name__)

    try:
        # Import os and litellm early
        import os
        from litellm import completion

        # Extract provider name from model
        # Model can come in formats:
        # - "nvidia_nim/meta/llama3-70b-instruct" (LiteLLM prefix format from frontend)
        # - "openai/gpt-oss-120b" (OpenAI provider with NVIDIA base)
        # - "meta/llama3-70b-instruct" (raw model name, need to detect provider)
        
        # First check if model has a provider prefix
        parts = model.split("/", 1) if "/" in model else [model, ""]
        potential_provider = parts[0]
        model_suffix = parts[1] if len(parts) > 1 else ""
        
        # Known LiteLLM provider prefixes
        litellm_providers = ["ollama", "openai", "openrouter", "anthropic", "nvidia_nim"]
        
        provider_name = None
        raw_model_name = model
        
        if potential_provider in litellm_providers:
            # Model has explicit provider prefix
            provider_name = potential_provider
            raw_model_name = model_suffix  # e.g., "meta/llama3-70b-instruct"
            logger.info(f"Detected provider prefix: {provider_name}, model: {raw_model_name}")
        else:
            # No provider prefix - try to detect from model name
            nvidia_prefixes = ["meta/", "mistralai/", "nvidia/", "google/", "codellama/", "deepseek/", "qwen/"]
            if any(model.startswith(p) for p in nvidia_prefixes):
                provider_name = "nvidia"
                raw_model_name = model
                logger.info(f"Detected NVIDIA model by prefix: {model}")
            else:
                provider_name = potential_provider
                raw_model_name = model
        
        # Map nvidia_nim to nvidia for database lookup
        db_provider_name = "nvidia" if provider_name == "nvidia_nim" else provider_name
        
        # Detect if this is a NVIDIA model being sent via OpenAI provider (Continue.dev style)
        is_nvidia_via_openai = False
        if provider_name == "openai" and raw_model_name:
            nvidia_prefixes = ["meta/", "mistralai/", "nvidia/", "google/", "codellama/", "deepseek/", "qwen/"]
            if any(raw_model_name.startswith(p) for p in nvidia_prefixes):
                is_nvidia_via_openai = True
                db_provider_name = "nvidia"
                logger.info(f"Detected NVIDIA model via OpenAI: {model}")

        logger.info(f"Testing model: {model}, provider: {provider_name}, db_provider: {db_provider_name}, nvidia_via_openai: {is_nvidia_via_openai}")

        # Get provider from database
        provider = db.query(LLMProvider).filter(LLMProvider.name == db_provider_name).first()

        if provider:
            logger.info(f"Found provider in DB: {db_provider_name}")
            # Decrypt API key if exists
            api_key = None
            if provider.api_key_encrypted:
                try:
                    api_key = decrypt_data(provider.api_key_encrypted)
                    logger.info(f"API key decrypted for {db_provider_name}")
                except Exception as e:
                    logger.warning(f"Failed to decrypt API key for {db_provider_name}: {e}")
                    api_key = None

            # Set API key in environment for LiteLLM BEFORE calling completion
            if api_key:
                if is_nvidia_via_openai:
                    # NVIDIA via OpenAI provider (Continue.dev style)
                    os.environ["OPENAI_API_KEY"] = api_key
                    os.environ["OPENAI_API_BASE"] = provider.api_url or "https://integrate.api.nvidia.com/v1/"
                    logger.info(f"Set OPENAI_API_KEY and OPENAI_API_BASE={os.environ['OPENAI_API_BASE']}")
                elif provider_name == "openrouter":
                    os.environ["OPENROUTER_API_KEY"] = api_key
                    logger.info("Set OPENROUTER_API_KEY")
                elif provider_name == "anthropic":
                    os.environ["ANTHROPIC_API_KEY"] = api_key
                    logger.info("Set ANTHROPIC_API_KEY")
                elif provider_name == "openai":
                    os.environ["OPENAI_API_KEY"] = api_key
                    logger.info("Set OPENAI_API_KEY")
                elif provider_name == "nvidia" or provider_name == "nvidia_nim":
                    os.environ["NVIDIA_NIM_API_KEY"] = api_key
                    # Set NVIDIA API base URL - ensure trailing slash for consistency
                    api_base = provider.api_url or "https://integrate.api.nvidia.com/v1/"
                    # Normalize: ensure exactly one trailing slash
                    api_base = api_base.rstrip('/') + '/'
                    os.environ["NVIDIA_NIM_API_BASE"] = api_base
                    logger.info(f"Set NVIDIA_NIM_API_KEY and NVIDIA_NIM_API_BASE={os.environ['NVIDIA_NIM_API_BASE']}")
            elif provider_name not in ["ollama", "nvidia", "nvidia_nim"]:
                logger.warning(f"No API key found for {db_provider_name}")
        else:
            logger.warning(f"Provider {db_provider_name} not found in database, trying without API key")

        # Check if using Ollama
        if model.startswith("ollama/"):
            import requests
            try:
                requests.get(OLLAMA_URL, timeout=2)
            except Exception as e:
                return templates.TemplateResponse("settings/llm_test_result.html", {
                    "request": request,
                    "success": False,
                    "error": f"Cannot connect to Ollama at {OLLAMA_URL}",
                    "hint": "Run 'ollama serve' in another terminal or install Ollama from ollama.com",
                    "model": model,
                    "time_ms": 0
                })

        # For nvidia_nim prefix, use the model as-is (LiteLLM handles it)
        # The frontend already sends "nvidia_nim/meta/llama3-70b-instruct"
        litellm_model = model
        
        logger.info(f"Calling completion API with model: {litellm_model}")

        response = completion(
            model=litellm_model,
            messages=[{"role": "user", "content": prompt}]
        )

        elapsed_ms = int((time.time() - start_time) * 1000)

        return templates.TemplateResponse("settings/llm_test_result.html", {
            "request": request,
            "success": True,
            "response": response.choices[0].message.content,
            "model": model,
            "time_ms": elapsed_ms,
            "tokens_used": response.usage.total_tokens if hasattr(response, 'usage') else None
        })

    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Test failed for {model}: {e}")
        return templates.TemplateResponse("settings/llm_test_result.html", {
            "request": request,
            "success": False,
            "error": str(e),
            "model": model,
            "time_ms": elapsed_ms,
            "hint": get_error_hint(e, model)
        })


def get_error_hint(error: Exception, model: str) -> str:
    """Provide helpful error hints"""
    error_msg = str(error).lower()
    
    if "connection" in error_msg or "refused" in error_msg:
        if "ollama" in model:
            return "Ollama is not running. Start it with: ollama serve"
        return "Cannot connect to API. Check your internet connection."
    
    if "api_key" in error_msg or "unauthorized" in error_msg:
        return "API key is missing or invalid. Configure it above."
    
    if "model" in error_msg or "not found" in error_msg:
        return f"Model '{model}' not found. Check the model name."
    
    if "timeout" in error_msg:
        return "Request timed out. The model may be loading or the server is slow."


# ============================================
# Claude Code OAuth Routes
# ============================================

@router.post("/{provider_id}/claude-code/import")
async def import_claude_code(
    provider_id: int,
    db: Session = Depends(get_db)
):
    """Import Claude Code OAuth credentials from CLI"""
    from backend.utils.claude_code_auth import import_claude_code_credentials
    from backend.security import encrypt_data
    from datetime import datetime, timezone
    
    provider = db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    # Import credentials
    success, error, token_info = import_claude_code_credentials()
    
    if not success:
        return {"success": False, "message": error}
    
    # Store encrypted tokens
    provider.auth_method = "claude_code_oauth"
    provider.oauth_token_encrypted = encrypt_data(token_info['access_token'])
    provider.oauth_refresh_token_encrypted = encrypt_data(token_info['refresh_token'])
    provider.oauth_expires_at = datetime.fromtimestamp(token_info['expires_at'] / 1000, tz=timezone.utc)
    provider.oauth_subscription_type = token_info['subscription_type']
    
    db.commit()
    
    return {
        "success": True,
        "message": f"Imported Claude Code credentials ({token_info['subscription_type']})",
        "subscription_type": token_info['subscription_type'],
        "expires_at": token_info['expires_at']
    }


@router.post("/{provider_id}/claude-code/refresh")
async def refresh_claude_code(
    provider_id: int,
    db: Session = Depends(get_db)
):
    """Refresh Claude Code OAuth token"""
    from backend.utils.claude_code_auth import refresh_claude_code_token, get_valid_oauth_token
    from backend.security import encrypt_data, decrypt_data
    from datetime import datetime, timezone
    
    provider = db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    if not provider.oauth_refresh_token_encrypted:
        return {"success": False, "message": "No refresh token available"}
    
    # Get refresh token
    refresh_token = decrypt_data(provider.oauth_refresh_token_encrypted)
    
    # Refresh
    new_access, new_refresh, new_expires_ms, sub_type = refresh_claude_code_token(refresh_token)
    
    if not new_access:
        return {"success": False, "message": "Failed to refresh token"}
    
    # Update database
    provider.oauth_token_encrypted = encrypt_data(new_access)
    provider.oauth_refresh_token_encrypted = encrypt_data(new_refresh)
    provider.oauth_expires_at = datetime.fromtimestamp(new_expires_ms / 1000, tz=timezone.utc)
    if sub_type:
        provider.oauth_subscription_type = sub_type
    
    db.commit()
    
    return {
        "success": True,
        "message": "Token refreshed successfully",
        "subscription_type": sub_type,
        "expires_at": new_expires_ms
    }


@router.get("/{provider_id}/claude-code/status")
async def claude_code_status(
    provider_id: int,
    db: Session = Depends(get_db)
):
    """Check Claude Code OAuth status"""
    from backend.utils.claude_code_auth import test_claude_code_connection, get_valid_oauth_token
    from backend.security import decrypt_data
    
    provider = db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    if provider.auth_method != 'claude_code_oauth':
        return {
            "configured": False,
            "message": "Claude Code OAuth not configured for this provider"
        }
    
    if not provider.oauth_token_encrypted:
        return {
            "configured": False,
            "message": "No OAuth token configured"
        }
    
    # Get valid token (may refresh)
    access_token, error = get_valid_oauth_token(provider)
    
    if not access_token:
        return {
            "configured": True,
            "valid": False,
            "message": f"Token error: {error}",
            "subscription_type": provider.oauth_subscription_type,
            "expires_at": provider.oauth_expires_at.isoformat() if provider.oauth_expires_at else None
        }
    
    # Test connection
    is_valid, message = test_claude_code_connection(access_token)
    
    return {
        "configured": True,
        "valid": is_valid,
        "message": message,
        "subscription_type": provider.oauth_subscription_type,
        "expires_at": provider.oauth_expires_at.isoformat() if provider.oauth_expires_at else None
    }
