"""
LLM Test Endpoint - Test AI provider connectivity

LAZY LOADING: LiteLLM is imported only when endpoint is called
Uses dedicated LLM thread pool to avoid blocking the event loop.
"""
from fastapi import APIRouter, Form
from typing import Optional
import time
import logging
import asyncio

from backend.services.ai_routing import resolve_configured_provider_selection
from backend.services.llm_service import _build_completion_kwargs

logger = logging.getLogger(__name__)
router = APIRouter()


def _blocking_llm_completion(kwargs: dict):
    """
    Run blocking LiteLLM completion in a thread.
    This function is synchronous and blocks only the thread, not the event loop.
    """
    from litellm import completion

    return completion(**kwargs)


@router.post("/test")
async def test_llm(
    prompt: str = Form(..., description="Test prompt to send to LLM"),
    model: Optional[str] = Form(None, description="Model to use"),
    provider_id: Optional[str] = Form(None, description="Configured provider id")
):
    """
    Test LLM connection with a simple prompt

    Returns the response and timing information
    
    Uses run_in_executor to avoid blocking the async event loop.
    """
    from backend.config import OLLAMA_URL, DEFAULT_LLM_MODEL

    if not model:
        model = DEFAULT_LLM_MODEL

    start_time = time.time()

    try:
        if provider_id:
            selection = resolve_configured_provider_selection(provider_id)
            configured_model = selection.model
            configured_provider = selection.provider
            litellm_model = model or configured_model.model_name
            kwargs = _build_completion_kwargs(
                configured_provider,
                configured_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
        else:
            litellm_model = model
            kwargs = {
                "model": litellm_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
            }

        logger.info(f"Testing model: {litellm_model}")

        # Check if using Ollama
        if litellm_model.startswith("ollama/"):
            # Verify Ollama is running
            import requests
            try:
                requests.get(OLLAMA_URL, timeout=2)
            except (requests.ConnectionError, requests.Timeout):
                return {
                    "success": False,
                    "error": f"Cannot connect to Ollama at {OLLAMA_URL}. Is it running?",
                    "hint": "Run 'ollama serve' in another terminal"
                }

        logger.info(f"Using LiteLLM model: {kwargs['model']}")

        # Run LLM call in dedicated thread pool (not the default one)
        from backend.services.llm_executor import get_llm_executor
        
        loop = asyncio.get_event_loop()
        executor = get_llm_executor()
        response = await asyncio.wait_for(
            loop.run_in_executor(
                executor,
                _blocking_llm_completion,
                kwargs,
            ),
            timeout=120.0  # 2 minute timeout
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
            "model": kwargs["model"] if "kwargs" in locals() else model,
            "time_ms": elapsed_ms,
            "hint": get_error_hint(e, kwargs["model"] if "kwargs" in locals() else model or "")
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
