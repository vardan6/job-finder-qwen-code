"""
LLM Service - AI-powered extraction and analysis

Uses LiteLLM native async (acompletion) for true non-blocking LLM calls.
"""
import json
import re
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session

from backend.models.llm_provider import LLMProvider, LLMModel
from backend.models.document import LLMFunctionMapping


def get_llm_for_function(db: Session, function_name: str) -> Optional[LLMModel]:
    """Get the LLM model configured for a specific function"""
    mapping = db.query(LLMFunctionMapping).filter(
        LLMFunctionMapping.function_name == function_name,
        LLMFunctionMapping.is_active == True
    ).first()

    if not mapping or not mapping.model_id:
        return None

    return mapping.model


async def call_llm(db: Session, model: LLMModel, prompt: str) -> Optional[str]:
    """
    Call LLM API using the specified model (native async).
    
    Uses LiteLLM's acompletion() for true async operation.
    """
    try:
        # Import litellm lazily
        from litellm import acompletion

        provider = model.provider
        if not provider:
            return None

        # Build the model identifier
        if provider.name == "ollama":
            # For Ollama, use host + model
            model_name = f"ollama/{model.model_name}"
            api_base = provider.api_url or "http://localhost:11434"
        else:
            # For other providers, add proper prefix for LiteLLM
            provider_prefixes = {
                "nvidia_nim": "nvidia_nim/",
                "nvidia": "nvidia/",
                "openrouter": "openrouter/",
                "anthropic": "anthropic/",
                "openai": "openai/",
            }
            prefix = provider_prefixes.get(provider.name, "")
            if prefix and not model.model_name.startswith(prefix):
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
            "messages": [{"role": "user", "content": prompt}],
        }

        if api_base:
            kwargs["api_base"] = api_base

        # Check for OAuth authentication (Claude Code)
        if hasattr(provider, 'auth_method') and provider.auth_method == 'claude_code_oauth':
            from backend.utils.claude_code_auth import get_valid_oauth_token
            access_token, error = get_valid_oauth_token(provider)

            if not access_token:
                print(f"OAuth token error: {error}")
                return None

            # Use OAuth token as API key for LiteLLM
            kwargs["api_key"] = access_token
        # Otherwise use API key if present (for non-Ollama providers)
        elif provider.api_key_encrypted and provider.name != "ollama":
            from backend.security import decrypt_data
            api_key = decrypt_data(provider.api_key_encrypted)
            if api_key:
                kwargs["api_key"] = api_key

        # Call the LLM (native async)
        response = await acompletion(**kwargs)

        if response and response.choices and len(response.choices) > 0:
            return response.choices[0].message.content

        return None

    except Exception as e:
        print(f"LLM call error: {e}")
        return None


# Skill extraction prompt
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
1. Extract only technical/硬 skills (programming languages, frameworks, tools, platforms, databases, etc.)
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
    Extract skills from text using AI (native async).

    Args:
        content: The text content to analyze (resume, profile, etc.)
        db: Optional database session for LLM model lookup

    Returns:
        List of skill dictionaries with keys: skill, category, years_experience
    """
    from litellm import acompletion

    try:
        # Build the prompt
        prompt = SKILL_EXTRACTION_PROMPT.format(content=content)

        result_text = None

        # Try configured model first
        if db:
            model = get_llm_for_function(db, "skill_extractor")

            # If no specific model, try to get any available Ollama model
            if not model:
                ollama = db.query(LLMProvider).filter(LLMProvider.name == "ollama").first()
                if ollama:
                    model = db.query(LLMModel).filter(
                        LLMModel.provider_id == ollama.id,
                        LLMModel.is_default_for_provider == True
                    ).first()

            # Try configured model
            if model:
                result_text = await call_llm(db, model, prompt)

        # Fallback to direct Ollama call if configured model failed
        if not result_text:
            try:
                response = await acompletion(
                    model="ollama/llama3",
                    messages=[{"role": "user", "content": prompt}],
                    api_base="http://localhost:11434"
                )
                result_text = response.choices[0].message.content if response else None
            except Exception as ollama_error:
                print(f"Direct Ollama fallback failed: {ollama_error}")
                return []

        if not result_text:
            return []

        # Extract JSON from response
        skills = extract_json_from_response(result_text)

        if isinstance(skills, list):
            # Validate and clean up skills
            validated_skills = []
            for skill in skills:
                if isinstance(skill, dict) and "skill" in skill:
                    validated_skills.append({
                        "skill": str(skill["skill"]).strip(),
                        "category": skill.get("category", "preferred"),
                        "years_experience": skill.get("years_experience")
                    })
            return validated_skills

        return []

    except Exception as e:
        print(f"Skill extraction error: {e}")
        return []


def extract_json_from_response(response: str) -> Any:
    """Extract JSON from LLM response (handles markdown code blocks)"""
    # Try to find JSON in markdown code blocks
    json_match = re.search(r'```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```', response, re.DOTALL)

    if json_match:
        json_str = json_match.group(1)
    else:
        # Try to find JSON object/array directly
        json_match = re.search(r'(\{.*?\}|\[.*?\])', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try parsing the whole response as JSON
            json_str = response

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None
