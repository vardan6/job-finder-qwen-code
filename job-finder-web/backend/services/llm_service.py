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
from backend.models.document import LLMFunctionMapping

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider helpers
# ---------------------------------------------------------------------------

_PROVIDER_PREFIXES = {
    "ollama": "ollama/",
    "groq": "",
    "nvidia_nim": "nvidia_nim/",
    "nvidia": "nvidia_nim/",
    "openrouter": "openrouter/",
    "anthropic": "anthropic/",
    "openai": "openai/",
}


def get_llm_for_function(db: Session, function_name: str) -> Optional[LLMModel]:
    """Get the LLM model configured for a specific function"""
    mapping = db.query(LLMFunctionMapping).filter(
        LLMFunctionMapping.function_name == function_name,
        LLMFunctionMapping.is_active == True
    ).first()

    if not mapping or not mapping.model_id:
        return None

    return mapping.model


def _build_completion_kwargs(
    provider: LLMProvider,
    model: LLMModel,
    messages: list,
    temperature: float = 0.7,
) -> dict:
    """Build kwargs dict for litellm.completion from provider + model."""
    if provider.name == "ollama":
        model_name = f"ollama/{model.model_name}"
        api_base = provider.api_url or "http://localhost:11434"
    elif provider.name == "groq":
        model_name = model.model_name
        api_base = provider.api_url or "https://api.groq.com/openai/v1"
    else:
        prefix = _PROVIDER_PREFIXES.get(provider.name, "")
        if prefix and not model.model_name.startswith(prefix):
            model_name = prefix + model.model_name
        else:
            model_name = model.model_name
        api_base = provider.api_url
        if api_base and api_base.endswith("/v1"):
            api_base = api_base[:-3]

    kwargs: dict = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
    }

    if api_base:
        kwargs["api_base"] = api_base

    # Authentication
    if hasattr(provider, "auth_method") and provider.auth_method == "claude_code_oauth":
        from backend.utils.claude_code_auth import get_valid_oauth_token
        access_token, error = get_valid_oauth_token(provider)
        if not access_token:
            logger.warning(f"OAuth token error: {error}")
        else:
            kwargs["api_key"] = access_token
    elif provider.api_key_encrypted and provider.name != "ollama":
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
    from litellm import acompletion

    response = await asyncio.wait_for(
        acompletion(**kwargs),
        timeout=timeout,
    )
    if response and response.choices and len(response.choices) > 0:
        return response.choices[0].message.content
    return None


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
    function_name: str = "ai_chat",
    model_override: Optional[str] = None,
    temperature: float = 0.7,
    db: Optional[Session] = None,
) -> Optional[str]:
    """
    Send a message to an LLM using the configured model for a function.

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
            model = get_llm_for_function(db, function_name)
            if not model or not model.provider:
                return None
            kwargs = _build_completion_kwargs(
                model.provider, model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
            )

        return await _async_completion(LLM_TIMEOUT_SECONDS, **kwargs)

    except asyncio.TimeoutError:
        logger.error(
            f"send_message timed out after {LLM_TIMEOUT_SECONDS}s "
            f"(function={function_name}). LLM provider may be unresponsive."
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

        # Try configured model first
        if db:
            model = get_llm_for_function(db, "skill_extractor")
            if not model:
                ollama = db.query(LLMProvider).filter(LLMProvider.name == "ollama").first()
                if ollama:
                    model = db.query(LLMModel).filter(
                        LLMModel.provider_id == ollama.id,
                        LLMModel.is_default_for_provider == True
                    ).first()
            if model:
                result_text = await call_llm(db, model, prompt)

        # Fallback to direct Ollama call
        if not result_text:
            try:
                result_text = await _async_completion(
                    LLM_TIMEOUT_SECONDS,
                    model="ollama/llama3",
                    messages=[{"role": "user", "content": prompt}],
                    api_base="http://localhost:11434",
                )
            except asyncio.TimeoutError:
                logger.warning(f"Direct Ollama fallback timed out after {LLM_TIMEOUT_SECONDS}s")
                return []
            except Exception as e:
                logger.warning(f"Direct Ollama fallback failed: {e}")
                return []

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
