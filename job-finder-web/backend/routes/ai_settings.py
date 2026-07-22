from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from backend.ai_capabilities import (
    JOB_FINDER_TOOL_CAPABILITIES,
    PROVIDER_CAPABILITIES,
    ROUTING_PURPOSE_LABELS,
    ROUTING_PURPOSES,
)
from backend.ai_config_store import load_ai_config, save_ai_config
from backend.ai_secret_store import SecretStore

router = APIRouter()


def _require_object(payload: Any, detail: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail=detail)
    return payload


@router.get("/api/ai-settings")
async def get_ai_settings() -> dict[str, Any]:
    config = load_ai_config()
    return {"ai_settings": config.ai_settings}


@router.post("/api/ai-settings")
async def save_ai_settings(payload: dict[str, Any]) -> JSONResponse:
    settings_payload = payload.get("ai_settings", payload)
    config = load_ai_config()
    config.raw["ai_settings"] = _require_object(
        settings_payload,
        "ai_settings must be an object",
    )
    save_ai_config(config)
    return JSONResponse({"ok": True, "ai_settings": config.raw["ai_settings"]})


@router.get("/api/llm-settings")
async def get_llm_settings() -> dict[str, Any]:
    config = load_ai_config()
    secret_store = SecretStore()
    providers = []
    for provider in config.llm_providers:
        if not isinstance(provider, dict):
            continue
        item = dict(provider)
        auth_mode = str(item.get("auth_mode", "env_var")).strip()
        secret_ref = str(item.get("secret_ref", "")).strip()
        item["has_stored_secret"] = (
            auth_mode == "stored_secret" and bool(secret_ref) and secret_store.has_secret(secret_ref)
        )
        providers.append(item)
    return {
        "providers": providers,
        "routing": config.model_routing,
        "routing_purposes": list(ROUTING_PURPOSES),
        "routing_labels": ROUTING_PURPOSE_LABELS,
        "capability_model": {
            "provider_capabilities": list(PROVIDER_CAPABILITIES),
            "job_finder_tool_capabilities": list(JOB_FINDER_TOOL_CAPABILITIES),
        },
    }


@router.put("/api/llm-settings")
async def save_llm_settings(payload: dict[str, Any]) -> JSONResponse:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="settings payload must be an object")

    providers_payload = payload.get("llm_providers", payload.get("providers", []))
    routing_payload = payload.get("model_routing", payload.get("routing", {}))

    if not isinstance(providers_payload, list):
        raise HTTPException(status_code=400, detail="llm_providers must be a list")
    if not isinstance(routing_payload, dict):
        raise HTTPException(status_code=400, detail="model_routing must be an object")

    config = load_ai_config()
    config.raw["llm_providers"] = providers_payload
    config.raw["model_routing"] = routing_payload
    save_ai_config(config)
    refreshed = load_ai_config(config.settings_path)
    secret_store = SecretStore()
    providers = []
    for provider in refreshed.llm_providers:
        if not isinstance(provider, dict):
            continue
        item = dict(provider)
        auth_mode = str(item.get("auth_mode", "env_var")).strip()
        secret_ref = str(item.get("secret_ref", "")).strip()
        item["has_stored_secret"] = (
            auth_mode == "stored_secret" and bool(secret_ref) and secret_store.has_secret(secret_ref)
        )
        providers.append(item)
    return JSONResponse(
        {
            "ok": True,
            "providers": providers,
            "routing": refreshed.model_routing,
        }
    )


@router.get("/api/ai-settings/export")
async def export_ai_settings() -> dict[str, Any]:
    """Export the full portable settings document (providers reference secrets
    by name only; actual secret values live in SecretStore and are never
    exported)."""
    config = load_ai_config()
    return {
        "ai_settings": config.ai_settings,
        "llm_providers": config.llm_providers,
        "model_routing": config.model_routing,
    }


@router.post("/api/ai-settings/import")
async def import_ai_settings(payload: dict[str, Any]) -> JSONResponse:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Settings document must be a JSON object")

    ai_settings = payload.get("ai_settings", {})
    providers_payload = payload.get("llm_providers", [])
    routing_payload = payload.get("model_routing", {})

    if not isinstance(ai_settings, dict):
        raise HTTPException(status_code=400, detail="ai_settings must be an object")
    if not isinstance(providers_payload, list):
        raise HTTPException(status_code=400, detail="llm_providers must be a list")
    if not isinstance(routing_payload, dict):
        raise HTTPException(status_code=400, detail="model_routing must be an object")

    for index, provider in enumerate(providers_payload):
        if not isinstance(provider, dict):
            raise HTTPException(status_code=400, detail=f"llm_providers[{index}] must be an object")
        missing = [
            field for field in ("id", "display_name", "provider_type", "model_id")
            if not str(provider.get(field, "")).strip()
        ]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"llm_providers[{index}] is missing required field(s): {', '.join(missing)}",
            )

    # Only mutate state after every check above has passed, so an invalid
    # document never partially overwrites the current settings.
    config = load_ai_config()
    config.raw["ai_settings"] = ai_settings
    config.raw["llm_providers"] = providers_payload
    config.raw["model_routing"] = routing_payload
    save_ai_config(config)
    refreshed = load_ai_config(config.settings_path)
    return JSONResponse(
        {
            "ok": True,
            "ai_settings": refreshed.ai_settings,
            "providers": refreshed.llm_providers,
            "routing": refreshed.model_routing,
        }
    )
