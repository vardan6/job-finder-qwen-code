"""
LLM Test Endpoint - Test AI provider connectivity

LAZY LOADING: LiteLLM is imported only when endpoint is called
"""
from fastapi import APIRouter, Form
from typing import Optional
import time
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/test")
async def test_llm(
    prompt: str = Form(..., description="Test prompt to send to LLM"),
    model: Optional[str] = Form(None, description="Model to use")
):
    """
    Test LLM connection with a simple prompt

    Returns the response and timing information
    """
    # LAZY IMPORT - Only import LiteLLM when endpoint is actually called
    from litellm import completion
    import os
    from backend.config import OLLAMA_URL, DEFAULT_LLM_MODEL

    if not model:
        model = DEFAULT_LLM_MODEL

    start_time = time.time()

    try:
        # Extract provider name from model
        provider_name = model.split("/")[0] if "/" in model else model
        
        # Detect NVIDIA models (frontend sends without provider prefix)
        nvidia_prefixes = ["meta/", "mistralai/", "nvidia/", "google/", "codellama/", "deepseek/"]
        is_nvidia_model = any(model.startswith(p) for p in nvidia_prefixes)
        
        if is_nvidia_model and provider_name not in ["ollama", "openrouter", "anthropic", "openai"]:
            provider_name = "nvidia"

        logger.info(f"Testing model: {model}, detected provider: {provider_name}")

        # Check if using Ollama
        if model.startswith("ollama/"):
            # Verify Ollama is running
            import requests
            try:
                requests.get(OLLAMA_URL, timeout=2)
            except:
                return {
                    "success": False,
                    "error": f"Cannot connect to Ollama at {OLLAMA_URL}. Is it running?",
                    "hint": "Run 'ollama serve' in another terminal"
                }

        # Format model name for LiteLLM
        litellm_model = model
        if provider_name == "nvidia":
            # NVIDIA requires nvidia_nim/ prefix for LiteLLM
            litellm_model = f"nvidia_nim/{model}"
            logger.info(f"Using LiteLLM model: {litellm_model}")

        # Call LLM
        response = completion(
            model=litellm_model,
            messages=[{"role": "user", "content": prompt}]
        )
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        return {
            "success": True,
            "response": response.choices[0].message.content,
            "model": model,
            "time_ms": elapsed_ms,
            "tokens_used": response.usage.total_tokens if hasattr(response, 'usage') else None
        }
        
    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        return {
            "success": False,
            "error": str(e),
            "model": model,
            "time_ms": elapsed_ms,
            "hint": get_error_hint(e, model)
        }


def get_error_hint(error: Exception, model: str) -> str:
    """Provide helpful error hints"""
    error_msg = str(error).lower()
    
    if "connection" in error_msg or "refused" in error_msg:
        if "ollama" in model:
            return "Ollama is not running. Start it with: ollama serve"
        return "Cannot connect to API. Check your internet connection."
    
    if "api_key" in error_msg or "unauthorized" in error_msg:
        return "API key is missing or invalid. Configure it in settings."
    
    if "model" in error_msg or "not found" in error_msg:
        return f"Model '{model}' not found. Check the model name."
    
    return "Check your configuration and try again."
