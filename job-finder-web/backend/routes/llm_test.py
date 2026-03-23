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
            # Model has explicit provider prefix - use as-is
            provider_name = potential_provider
            raw_model_name = model_suffix
            logger.info(f"Detected provider prefix: {provider_name}, model: {raw_model_name}")
        else:
            # No provider prefix - use as potential provider
            provider_name = potential_provider
            raw_model_name = model
        
        logger.info(f"Testing model: {model}, provider: {provider_name}")

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

        # For models with explicit provider prefix (like nvidia_nim/), use as-is
        # LiteLLM will handle the routing correctly
        litellm_model = model
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
