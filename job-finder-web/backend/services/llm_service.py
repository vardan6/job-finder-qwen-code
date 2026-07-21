"""
LLM Service - AI-powered extraction and analysis

Uses LiteLLM's native async API so LLM requests do not block the FastAPI
event loop.
"""
import asyncio
import json
import logging
import re
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session

from backend.models.llm_provider import LLMProvider, LLMModel
from backend.services.ai_routing import resolve_chat_model_selection

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider helpers
# ---------------------------------------------------------------------------

_PROVIDER_PREFIXES = {
    "ollama": "ollama/",
    "nvidia_nim": "nvidia_nim/",
    "nvidia": "nvidia_nim/",
    "openrouter": "openrouter/",
    "anthropic": "anthropic/",
    # These providers expose an OpenAI-compatible chat-completions endpoint.
    # Their configured base URL and credential are passed directly below.
    "openai": "openai/",
    "openai_compatible": "openai/",
    "gemini": "openai/",
    "groq": "openai/",
    "mistral": "openai/",
    "cohere": "openai/",
    "together": "openai/",
    "huggingface": "openai/",
    "lm_studio": "openai/",
}


def _normalize_api_base(provider_name: str, api_base: str | None) -> str | None:
    """
    Normalize provider API bases without changing semantic path prefixes.

    Many OpenAI-compatible providers require a specific base path (often `/v1`).
    Rewriting that path can cause 404s. Keep user-configured paths intact.
    """
    if not api_base:
        return None
    return api_base.strip() or None


def _build_completion_kwargs(
    provider: LLMProvider,
    model: LLMModel,
    messages: list,
    temperature: float = 0.7,
) -> dict:
    """Build kwargs dict for litellm.completion from provider + model."""
    provider_name = str(getattr(provider, "name", "") or "").strip().lower()
    provider_api_url = getattr(provider, "api_url", None)
    model_name_raw = str(getattr(model, "model_name", "") or "").strip()

    if provider_name == "ollama":
        model_name = f"ollama/{model_name_raw}"
        api_base = provider_api_url or "http://localhost:11434"
    elif provider_name == "groq":
        prefix = _PROVIDER_PREFIXES[provider_name]
        model_name = model_name_raw if model_name_raw.startswith(prefix) else prefix + model_name_raw
        api_base = provider_api_url or "https://api.groq.com/openai/v1"
    else:
        prefix = _PROVIDER_PREFIXES.get(provider_name, "")
        if prefix and not model_name_raw.startswith(prefix):
            model_name = prefix + model_name_raw
        else:
            model_name = model_name_raw
        api_base = provider_api_url

    kwargs: dict = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
    }

    normalized_api_base = _normalize_api_base(provider.name, api_base)
    if normalized_api_base:
        kwargs["api_base"] = normalized_api_base

    # Authentication
    if getattr(provider, "api_key", None) and provider_name != "ollama":
        kwargs["api_key"] = provider.api_key
    elif hasattr(provider, "auth_method") and provider.auth_method == "claude_code_oauth":
        from backend.utils.claude_code_auth import get_valid_oauth_token
        access_token, error = get_valid_oauth_token(provider)
        if not access_token:
            logger.warning(f"OAuth token error: {error}")
        else:
            kwargs["api_key"] = access_token
    elif getattr(provider, "api_key_encrypted", None) and provider_name != "ollama":
        from backend.security import decrypt_data
        api_key = decrypt_data(provider.api_key_encrypted)
        if api_key:
            kwargs["api_key"] = api_key

    return kwargs


# ---------------------------------------------------------------------------
# Core LLM call
# ---------------------------------------------------------------------------

async def _async_completion(timeout: float, **kwargs) -> Optional[str]:
    """Run LiteLLM async completion with a timeout."""
    response = await _async_completion_response(timeout, **kwargs)
    if response and response.choices and len(response.choices) > 0:
        return response.choices[0].message.content
    return None


async def _async_completion_response(timeout: float, **kwargs) -> Any:
    """Run LiteLLM async completion with a timeout and return the raw response."""
    from litellm import acompletion

    return await asyncio.wait_for(
        acompletion(**kwargs),
        timeout=timeout,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def call_llm(db: Session, model: LLMModel, prompt: str) -> Optional[str]:
    """
    Call LLM API using the specified model.

    Uses LiteLLM's async API so the event loop stays free.
    """
    from backend.config import LLM_TIMEOUT_SECONDS

    provider = model.provider
    if not provider:
        return None

    kwargs = _build_completion_kwargs(
        provider, model,
        messages=[{"role": "user", "content": prompt}],
    )

    try:
        return await _async_completion(LLM_TIMEOUT_SECONDS, **kwargs)
    except asyncio.TimeoutError:
        logger.error(
            f"LLM call timed out after {LLM_TIMEOUT_SECONDS}s. "
            "Check that your LLM provider is running and responsive."
        )
        return None
    except Exception as e:
        logger.error(f"LLM call error: {e}")
        return None


async def send_message(
    prompt: str,
    model_override: Optional[str] = None,
    temperature: float = 0.7,
    db: Optional[Session] = None,
    routing_purpose: Optional[str] = None,
) -> Optional[str]:
    """
    Send a message using an explicitly requested model or a configured routing purpose.

    Uses LiteLLM's async API so the event loop stays free.
    """
    from backend.config import LLM_TIMEOUT_SECONDS

    try:
        if model_override:
            kwargs: dict = {
                "model": model_override,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
            }
        else:
            if not db:
                return None
            if routing_purpose:
                selection = resolve_chat_model_selection(db, purpose=routing_purpose)
                model = selection.model
                provider = selection.provider
            else:
                return None
            kwargs = _build_completion_kwargs(
                provider, model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
            )

        return await _async_completion(LLM_TIMEOUT_SECONDS, **kwargs)

    except asyncio.TimeoutError:
        logger.error(
            f"send_message timed out after {LLM_TIMEOUT_SECONDS}s "
            f"(routing_purpose={routing_purpose}). LLM provider may be unresponsive."
        )
        return None
    except Exception as e:
        logger.error(f"send_message error: {e}")
        return None


# ---------------------------------------------------------------------------
# Skill extraction
# ---------------------------------------------------------------------------

SKILL_EXTRACTION_PROMPT = """
You are an expert at extracting technical skills from resumes and job descriptions.

Analyze the following text and extract all technical skills mentioned. Categorize each skill as:
- "required": Core/essential skills that are fundamental for the role (mentioned multiple times, listed as requirements)
- "preferred": Nice-to-have skills, bonus qualifications, or secondary technologies

For each skill, also estimate years of experience if possible based on context (null if cannot determine).

Return the result as a JSON array in this exact format:
[
  {{"skill": "Python", "category": "required", "years_experience": 5}},
  {{"skill": "FastAPI", "category": "required", "years_experience": 3}},
  {{"skill": "Docker", "category": "preferred", "years_experience": 2}},
  ...
]

Rules:
1. Extract only technical skills (programming languages, frameworks, tools, platforms, databases, etc.)
2. Do not include soft skills (communication, leadership, etc.)
3. Group related skills (e.g., "AWS" instead of listing every AWS service separately, unless specific services are emphasized)
4. Be comprehensive but avoid duplicates
5. Use standard skill names (e.g., "PostgreSQL" not "Postgres DB")

Text to analyze:
---
{content}
---

Extract skills as JSON:
"""


async def extract_skills_from_text(content: str, db: Optional[Session] = None) -> List[Dict[str, Any]]:
    """
    Extract skills from text using AI.

    Uses LiteLLM's async API so the event loop stays free.
    """
    from backend.config import LLM_TIMEOUT_SECONDS

    try:
        prompt = SKILL_EXTRACTION_PROMPT.format(content=content)
        result_text = None

        # Resolve the configured Candidate Analysis provider and model.
        if db:
            try:
                selection = resolve_chat_model_selection(db, purpose="candidate_analysis")
                model = selection.model
                provider = selection.provider
            except Exception:
                return []
            kwargs = _build_completion_kwargs(
                provider,
                model,
                messages=[{"role": "user", "content": prompt}],
            )
            result_text = await _async_completion(LLM_TIMEOUT_SECONDS, **kwargs)

        if not result_text:
            return []

        skills = extract_json_from_response(result_text)
        if isinstance(skills, list):
            validated_skills = []
            for skill in skills:
                if isinstance(skill, dict) and "skill" in skill:
                    validated_skills.append({
                        "skill": str(skill["skill"]).strip(),
                        "category": skill.get("category", "preferred"),
                        "years_experience": skill.get("years_experience"),
                    })
            return validated_skills

        return []

    except Exception as e:
        logger.error(f"Skill extraction error: {e}")
        return []


# ---------------------------------------------------------------------------
# JSON extraction helper
# ---------------------------------------------------------------------------

def extract_json_from_response(response: str) -> Any:
    """Extract JSON from LLM response (handles markdown code blocks)"""
    json_match = re.search(r'```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```', response, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_match = re.search(r'(\{.*?\}|\[.*?\])', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = response

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None
