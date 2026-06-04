from __future__ import annotations

import json

from backend.ai_config_store import ROUTING_PURPOSES, load_ai_config, save_ai_config


def test_load_ai_config_provides_default_provider_and_routing(tmp_path) -> None:
    config = load_ai_config(tmp_path / "ai-settings.json")

    assert len(config.llm_providers) == 1
    assert config.llm_providers[0]["provider_type"] == "ollama"
    assert set(config.model_routing) == set(ROUTING_PURPOSES)
    assert all(rule["primary_provider_id"] == "provider-default-ollama" for rule in config.model_routing.values())
    assert all(rule["allow_runtime_override"] is True for rule in config.model_routing.values())


def test_save_ai_config_normalizes_invalid_routing_entries(tmp_path) -> None:
    settings_path = tmp_path / "ai-settings.json"
    config = load_ai_config(settings_path)
    config.raw["model_routing"] = {
        "general_chat": {
            "primary_provider_id": "missing-provider",
            "fallback_provider_ids": ["provider-default-ollama", "missing-provider"],
        }
    }

    save_ai_config(config)

    payload = json.loads(settings_path.read_text(encoding="utf-8"))
    rule = payload["model_routing"]["general_chat"]
    assert rule["primary_provider_id"] == "provider-default-ollama"
    assert rule["fallback_provider_ids"] == []
    assert rule["allow_runtime_override"] is True


def test_load_ai_config_preserves_valid_provider_specific_routing(tmp_path) -> None:
    settings_path = tmp_path / "ai-settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "llm_providers": [
                    {
                        "id": "provider-a",
                        "display_name": "Provider A",
                        "provider_type": "ollama",
                        "auth_mode": "none",
                        "secret_ref": "",
                        "base_url": "http://localhost:11434",
                        "model_id": "llama3:latest",
                        "enabled": True,
                        "capabilities": ["chat"],
                        "context_window": None,
                    },
                    {
                        "id": "provider-b",
                        "display_name": "Provider B",
                        "provider_type": "openrouter",
                        "auth_mode": "env_var",
                        "secret_ref": "OPENROUTER_API_KEY",
                        "base_url": "https://openrouter.ai/api/v1",
                        "model_id": "openai/gpt-4.1-mini",
                        "enabled": True,
                        "capabilities": ["chat", "tools"],
                        "context_window": 128000,
                    },
                ],
                "model_routing": {
                    "agent": {
                        "primary_provider_id": "provider-b",
                        "fallback_provider_ids": ["provider-a"],
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    config = load_ai_config(settings_path)

    assert config.model_routing["agent"]["primary_provider_id"] == "provider-b"
    assert config.model_routing["agent"]["fallback_provider_ids"] == ["provider-a"]
    assert config.model_routing["agent"]["allow_runtime_override"] is True


def test_load_ai_config_normalizes_provider_capabilities(tmp_path) -> None:
    settings_path = tmp_path / "ai-settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "llm_providers": [
                    {
                        "id": "provider-a",
                        "display_name": "Provider A",
                        "provider_type": "openrouter",
                        "auth_mode": "env_var",
                        "secret_ref": "OPENROUTER_API_KEY",
                        "base_url": "https://openrouter.ai/api/v1",
                        "model_id": "openai/gpt-4.1-mini",
                        "enabled": True,
                        "capabilities": ["chat", "tools", "invalid", "chat"],
                        "context_window": 128000,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    config = load_ai_config(settings_path)

    assert config.llm_providers[0]["capabilities"] == ["chat", "tools"]
