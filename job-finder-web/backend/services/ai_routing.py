from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from backend.ai_config_store import load_ai_config
from backend.ai_secret_store import SecretStore
from backend.models.llm_provider import LLMModel, LLMProvider


@dataclass(slots=True)
class RuntimeProvider:
    id: str
    name: str
    display_name: str
    api_url: str | None
    auth_mode: str
    secret_ref: str
    api_key: str | None = None
    max_output_tokens: int | None = None


@dataclass(slots=True)
class RuntimeModel:
    id: str
    model_name: str
    display_name: str
    provider: RuntimeProvider


@dataclass(slots=True)
class RoutingSelection:
    provider: Any
    model: Any
    source: str
    configured_provider_id: str = ""


def _normalize_provider_type(value: object) -> str:
    return str(value or "").strip().lower()


def _find_configured_provider(provider_id: str) -> dict[str, object] | None:
    clean_id = str(provider_id or "").strip()
    if not clean_id:
        return None
    config = load_ai_config()
    return next(
        (
            provider
            for provider in config.llm_providers
            if isinstance(provider, dict) and str(provider.get("id", "")).strip() == clean_id
        ),
        None,
    )


def _resolve_api_key(provider_cfg: dict[str, object]) -> str | None:
    auth_mode = str(provider_cfg.get("auth_mode", "")).strip().lower() or "none"
    secret_ref = str(provider_cfg.get("secret_ref", "")).strip()
    if auth_mode == "none":
        return None
    if not secret_ref:
        return None
    if auth_mode == "stored_secret":
        try:
            return SecretStore().get_secret(secret_ref)
        except KeyError:
            return None
    value = os.getenv(secret_ref, "").strip()
    return value or None


def _credential_error(provider_cfg: dict[str, object]) -> str | None:
    auth_mode = str(provider_cfg.get("auth_mode", "")).strip().lower() or "none"
    if auth_mode == "none":
        return None
    secret_ref = str(provider_cfg.get("secret_ref", "")).strip()
    display_name = str(provider_cfg.get("display_name", "")).strip() or str(provider_cfg.get("id", "")).strip() or "provider"
    if not secret_ref:
        return f"{display_name} is missing its credential reference"
    if _resolve_api_key(provider_cfg):
        return None
    if auth_mode == "stored_secret":
        return f"{display_name} is missing its stored secret ({secret_ref})"
    return f"{display_name} is missing its environment variable ({secret_ref})"


def _selection_from_provider_cfg(
    provider_cfg: dict[str, object],
    *,
    source: str,
    require_credentials: bool = True,
) -> RoutingSelection | None:
    provider_id = str(provider_cfg.get("id", "")).strip()
    provider_type = _normalize_provider_type(provider_cfg.get("provider_type"))
    model_name = str(provider_cfg.get("model_id", "")).strip()
    if not provider_id or not provider_type or not model_name:
        return None
    if not provider_cfg.get("enabled", True):
        return None

    api_key = _resolve_api_key(provider_cfg)
    if require_credentials and _credential_error(provider_cfg):
        return None

    try:
        max_output_tokens = int(provider_cfg.get("max_output_tokens") or 0) or None
    except (TypeError, ValueError):
        max_output_tokens = None

    provider = RuntimeProvider(
        id=provider_id,
        name=provider_type,
        display_name=str(provider_cfg.get("display_name", "")).strip() or provider_type,
        api_url=str(provider_cfg.get("base_url", "")).strip() or None,
        auth_mode=str(provider_cfg.get("auth_mode", "")).strip().lower() or "none",
        secret_ref=str(provider_cfg.get("secret_ref", "")).strip(),
        api_key=api_key,
        max_output_tokens=max_output_tokens,
    )
    model = RuntimeModel(
        id=provider_id,
        model_name=model_name,
        display_name=model_name,
        provider=provider,
    )
    return RoutingSelection(
        provider=provider,
        model=model,
        source=source,
        configured_provider_id=provider_id,
    )


def _selection_from_legacy_model(model: LLMModel, *, configured_provider_id: str = "", source: str = "explicit_model") -> RoutingSelection:
    if not model.provider:
        raise ValueError("Model has no provider configured")
    return RoutingSelection(
        provider=model.provider,
        model=model,
        source=source,
        configured_provider_id=configured_provider_id,
    )


def _match_config_provider_for_db_model(provider: LLMProvider, model: LLMModel) -> dict[str, object] | None:
    config = load_ai_config()
    provider_name = _normalize_provider_type(provider.name)
    model_name = str(model.model_name or "").strip()
    api_url = str(provider.api_url or "").strip()

    exact_api_matches: list[dict[str, object]] = []
    generic_matches: list[dict[str, object]] = []
    for provider_cfg in config.llm_providers:
        if not isinstance(provider_cfg, dict):
            continue
        if _normalize_provider_type(provider_cfg.get("provider_type")) != provider_name:
            continue
        if str(provider_cfg.get("model_id", "")).strip() != model_name:
            continue
        cfg_base_url = str(provider_cfg.get("base_url", "")).strip()
        if api_url and cfg_base_url == api_url:
            exact_api_matches.append(provider_cfg)
        else:
            generic_matches.append(provider_cfg)
    if exact_api_matches:
        return exact_api_matches[0]
    if generic_matches:
        return generic_matches[0]
    return None


def _selection_from_db_model(db: Session, model_id: int) -> RoutingSelection:
    explicit_model = db.query(LLMModel).filter(LLMModel.id == model_id, LLMModel.is_active == True).first()
    if not explicit_model:
        raise ValueError("Model not found")
    if not explicit_model.provider or not explicit_model.provider.is_active:
        raise ValueError("Model has no provider configured")

    provider_cfg = _match_config_provider_for_db_model(explicit_model.provider, explicit_model)
    if provider_cfg:
        selection = _selection_from_provider_cfg(provider_cfg, source="explicit_model_config_match")
        if selection:
            return selection

    return _selection_from_legacy_model(explicit_model)


def _routing_rule(purpose: str) -> tuple[dict[str, object], list[dict[str, object]]]:
    config = load_ai_config()
    routing_rule = config.model_routing.get(purpose, {}) if isinstance(config.model_routing, dict) else {}
    providers = [provider for provider in config.llm_providers if isinstance(provider, dict)]
    return routing_rule if isinstance(routing_rule, dict) else {}, providers


def _resolve_from_routing_order(
    purpose: str,
    *,
    exclude_provider_ids: set[str] | None = None,
) -> RoutingSelection | None:
    routing_rule, providers = _routing_rule(purpose)
    provider_by_id = {
        str(provider.get("id", "")).strip(): provider
        for provider in providers
        if str(provider.get("id", "")).strip()
    }
    ordered_provider_ids: list[str] = []
    primary_id = str(routing_rule.get("primary_provider_id", "")).strip()
    if primary_id:
        ordered_provider_ids.append(primary_id)
    for fallback_id in routing_rule.get("fallback_provider_ids", []):
        clean_id = str(fallback_id).strip()
        if clean_id and clean_id not in ordered_provider_ids:
            ordered_provider_ids.append(clean_id)

    excluded = exclude_provider_ids or set()
    for provider_id in ordered_provider_ids:
        if provider_id in excluded:
            continue
        provider_cfg = provider_by_id.get(provider_id)
        if not provider_cfg:
            continue
        selection = _selection_from_provider_cfg(provider_cfg, source="routing")
        if selection:
            return selection
    return None


def resolve_configured_provider_selection(configured_provider_id: str) -> RoutingSelection:
    provider_cfg = _find_configured_provider(configured_provider_id)
    if not provider_cfg:
        raise ValueError("Configured provider not found")
    if not provider_cfg.get("enabled", True):
        raise ValueError("Configured provider is disabled")
    credential_error = _credential_error(provider_cfg)
    if credential_error:
        raise ValueError(credential_error)
    selection = _selection_from_provider_cfg(provider_cfg, source="configured_provider")
    if not selection:
        raise ValueError("Configured provider is incomplete")
    return selection


def resolve_chat_model_selection(
    db: Session,
    *,
    purpose: str,
    model_id: int | None = None,
    configured_provider_id: str | None = None,
) -> RoutingSelection:
    routing_rule, _providers = _routing_rule(purpose)
    allow_runtime_override = bool((routing_rule or {}).get("allow_runtime_override", True))

    if model_id is not None:
        if not allow_runtime_override:
            raise ValueError(f"Runtime model override is disabled for purpose '{purpose}'")
        return _selection_from_db_model(db, model_id)

    requested_provider_id = str(configured_provider_id or "").strip()
    if requested_provider_id:
        if not allow_runtime_override:
            routing_primary = str((routing_rule or {}).get("primary_provider_id", "")).strip()
            if requested_provider_id != routing_primary:
                raise ValueError(f"Runtime model override is disabled for purpose '{purpose}'")
            requested_provider_id = routing_primary

        try:
            return resolve_configured_provider_selection(requested_provider_id)
        except ValueError:
            fallback_from_routing = _resolve_from_routing_order(
                purpose,
                exclude_provider_ids={requested_provider_id},
            )
            if fallback_from_routing:
                return RoutingSelection(
                    provider=fallback_from_routing.provider,
                    model=fallback_from_routing.model,
                    source="routing_fallback_from_explicit_provider",
                    configured_provider_id=fallback_from_routing.configured_provider_id,
                )

    selection_from_routing = _resolve_from_routing_order(purpose)
    if selection_from_routing:
        return selection_from_routing

    raise ValueError(f"No usable configured providers available for purpose '{purpose}'")
