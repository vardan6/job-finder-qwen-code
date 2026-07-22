from __future__ import annotations

import json

from backend.ai_config_store import load_ai_config, save_ai_config
from backend.services.ai_routing import resolve_configured_provider_selection


def test_configured_provider_max_output_tokens_threads_into_runtime_provider(tmp_path) -> None:
    settings_path = tmp_path / "ai-settings.json"
    config = load_ai_config(settings_path)
    config.raw["llm_providers"][0]["max_output_tokens"] = 512
    save_ai_config(config)

    payload = json.loads(settings_path.read_text(encoding="utf-8"))
    assert payload["llm_providers"][0]["max_output_tokens"] == 512

    import backend.ai_config_store as ai_config_store
    original_path = ai_config_store.default_ai_settings_path
    ai_config_store.default_ai_settings_path = lambda: settings_path
    try:
        selection = resolve_configured_provider_selection("provider-default-ollama")
    finally:
        ai_config_store.default_ai_settings_path = original_path

    assert selection.provider.max_output_tokens == 512


def test_configured_provider_without_cap_leaves_max_output_tokens_none(tmp_path) -> None:
    settings_path = tmp_path / "ai-settings.json"
    load_ai_config(settings_path)  # materialize defaults on disk is not required; just resolve directly

    import backend.ai_config_store as ai_config_store
    original_path = ai_config_store.default_ai_settings_path
    ai_config_store.default_ai_settings_path = lambda: settings_path
    try:
        selection = resolve_configured_provider_selection("provider-default-ollama")
    finally:
        ai_config_store.default_ai_settings_path = original_path

    assert selection.provider.max_output_tokens is None
