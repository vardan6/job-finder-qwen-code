from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.ai_capabilities import PROVIDER_CAPABILITIES, ROUTING_PURPOSES
from backend.config import DATA_DIR

DEFAULT_AI_SETTINGS: dict[str, Any] = {
    "mutation_policy": "approve_writes",
}

DEFAULT_LLM_PROVIDERS: list[dict[str, Any]] = [
    {
        "id": "provider-default-ollama",
        "display_name": "Ollama Local",
        "provider_type": "ollama",
        "auth_mode": "none",
        "secret_ref": "",
        "base_url": "http://localhost:11434",
        "model_id": "llama3:latest",
        "enabled": True,
        "capabilities": ["chat"],
        "context_window": None,
        "max_output_tokens": None,
    }
]

DEFAULT_CONFIG: dict[str, Any] = {
    "ai_settings": DEFAULT_AI_SETTINGS,
    "llm_providers": DEFAULT_LLM_PROVIDERS,
    "model_routing": {},
}


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in patch.items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def normalize_provider(provider: Any) -> dict[str, Any] | None:
    if not isinstance(provider, dict):
        return None

    normalized = copy.deepcopy(provider)
    capabilities: list[str] = []
    seen: set[str] = set()
    for item in normalized.get("capabilities", []):
        capability = str(item).strip().lower()
        if capability and capability in PROVIDER_CAPABILITIES and capability not in seen:
            capabilities.append(capability)
            seen.add(capability)
    normalized["capabilities"] = capabilities or ["chat"]
    return normalized


def default_model_routing(providers: list[dict[str, Any]]) -> dict[str, Any]:
    default_provider = next(
        (
            str(provider.get("id", "")).strip()
            for provider in providers
            if isinstance(provider, dict) and provider.get("enabled", True) and str(provider.get("id", "")).strip()
        ),
        "",
    )
    return {
        purpose: {
            "primary_provider_id": default_provider,
            "fallback_provider_ids": [],
            "allow_runtime_override": True,
        }
        for purpose in ROUTING_PURPOSES
    }


def normalize_routing(routing: Any, providers: list[dict[str, Any]]) -> dict[str, Any]:
    valid_provider_ids = {
        str(provider.get("id", "")).strip()
        for provider in providers
        if isinstance(provider, dict) and str(provider.get("id", "")).strip()
    }
    normalized = default_model_routing(providers)
    if not isinstance(routing, dict):
        return normalized

    for purpose in ROUTING_PURPOSES:
        raw_rule = routing.get(purpose, {})
        if not isinstance(raw_rule, dict):
            continue
        primary_id = str(raw_rule.get("primary_provider_id", "")).strip()
        fallback_ids = [
            provider_id
            for provider_id in (
                str(item).strip() for item in raw_rule.get("fallback_provider_ids", []) if str(item).strip()
            )
            if provider_id in valid_provider_ids
        ]
        if primary_id not in valid_provider_ids:
            primary_id = normalized[purpose]["primary_provider_id"]
        fallback_ids = [provider_id for provider_id in fallback_ids if provider_id != primary_id]
        normalized[purpose] = {
            "primary_provider_id": primary_id,
            "fallback_provider_ids": fallback_ids,
            "allow_runtime_override": bool(raw_rule.get("allow_runtime_override", True)),
        }
    return normalized


@dataclass(slots=True)
class AIConfig:
    raw: dict[str, Any]
    settings_path: Path

    @property
    def ai_settings(self) -> dict[str, Any]:
        value = self.raw.get("ai_settings", {})
        return value if isinstance(value, dict) else {}

    @property
    def llm_providers(self) -> list[dict[str, Any]]:
        value = self.raw.get("llm_providers", [])
        return value if isinstance(value, list) else []

    @property
    def model_routing(self) -> dict[str, Any]:
        value = self.raw.get("model_routing", {})
        return value if isinstance(value, dict) else {}


def default_ai_settings_path() -> Path:
    return Path(os.getenv("AI_SETTINGS_PATH", DATA_DIR / "ai-settings.json"))


def load_ai_config(path: str | Path | None = None) -> AIConfig:
    settings_path = Path(path) if path else default_ai_settings_path()
    data: dict[str, Any] = {}
    if settings_path.exists():
        with open(settings_path, encoding="utf-8") as fh:
            loaded = json.load(fh)
        if isinstance(loaded, dict):
            data = loaded

    merged = _deep_merge(DEFAULT_CONFIG, data)
    providers = merged.get("llm_providers")
    if not isinstance(providers, list) or not providers:
        providers = copy.deepcopy(DEFAULT_LLM_PROVIDERS)
    normalized_providers = [provider for provider in (normalize_provider(item) for item in providers) if provider]
    if not normalized_providers:
        normalized_providers = copy.deepcopy(DEFAULT_LLM_PROVIDERS)
    merged["llm_providers"] = normalized_providers
    merged["model_routing"] = normalize_routing(merged.get("model_routing"), normalized_providers)
    return AIConfig(raw=merged, settings_path=settings_path)


def save_ai_config(config: AIConfig) -> None:
    config.settings_path.parent.mkdir(parents=True, exist_ok=True)
    payload = copy.deepcopy(config.raw)
    providers = payload.get("llm_providers", [])
    normalized_providers = [provider for provider in (normalize_provider(item) for item in providers) if provider]
    payload["llm_providers"] = normalized_providers or copy.deepcopy(DEFAULT_LLM_PROVIDERS)
    payload["model_routing"] = normalize_routing(
        payload.get("model_routing"),
        payload["llm_providers"],
    )
    with open(config.settings_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")
