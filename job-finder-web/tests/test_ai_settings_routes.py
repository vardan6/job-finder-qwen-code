from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routes.ai_settings import router


def create_client(tmp_path) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides = {}
    return TestClient(app)


def test_get_ai_settings_returns_default_payload(tmp_path, monkeypatch) -> None:
    settings_path = tmp_path / "ai-settings.json"
    monkeypatch.setenv("AI_SETTINGS_PATH", str(settings_path))

    client = create_client(tmp_path)
    response = client.get("/api/ai-settings")

    assert response.status_code == 200
    assert response.json() == {"ai_settings": {"mutation_policy": "approve_writes"}}


def test_post_ai_settings_persists_payload(tmp_path, monkeypatch) -> None:
    settings_path = tmp_path / "ai-settings.json"
    monkeypatch.setenv("AI_SETTINGS_PATH", str(settings_path))

    client = create_client(tmp_path)
    response = client.post("/api/ai-settings", json={"ai_settings": {"mutation_policy": "read_only"}})

    assert response.status_code == 200
    assert response.json() == {"ok": True, "ai_settings": {"mutation_policy": "read_only"}}
    payload = json.loads(settings_path.read_text(encoding="utf-8"))
    assert payload["ai_settings"] == {"mutation_policy": "read_only"}


def test_put_llm_settings_normalizes_and_persists_payload(tmp_path, monkeypatch) -> None:
    settings_path = tmp_path / "ai-settings.json"
    monkeypatch.setenv("AI_SETTINGS_PATH", str(settings_path))

    client = create_client(tmp_path)
    response = client.put(
        "/api/llm-settings",
        json={
            "providers": [
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
                }
            ],
            "routing": {
                "general_chat": {
                    "primary_provider_id": "missing-provider",
                    "fallback_provider_ids": ["provider-a"],
                }
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["providers"][0]["id"] == "provider-a"
    assert body["routing"]["general_chat"] == {
        "primary_provider_id": "provider-a",
        "fallback_provider_ids": [],
        "allow_runtime_override": True,
    }


def test_put_llm_settings_preserves_fallback_order(tmp_path, monkeypatch) -> None:
    settings_path = tmp_path / "ai-settings.json"
    monkeypatch.setenv("AI_SETTINGS_PATH", str(settings_path))

    client = create_client(tmp_path)
    response = client.put(
        "/api/llm-settings",
        json={
            "providers": [
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
                    "auth_mode": "none",
                    "secret_ref": "",
                    "base_url": "https://openrouter.ai/api/v1",
                    "model_id": "openai/gpt-4.1-mini",
                    "enabled": True,
                    "capabilities": ["chat"],
                    "context_window": 128000,
                },
                {
                    "id": "provider-c",
                    "display_name": "Provider C",
                    "provider_type": "openai",
                    "auth_mode": "none",
                    "secret_ref": "",
                    "base_url": "https://api.openai.com/v1",
                    "model_id": "gpt-4.1-mini",
                    "enabled": True,
                    "capabilities": ["chat"],
                    "context_window": 128000,
                },
            ],
            "routing": {
                "general_chat": {
                    "primary_provider_id": "provider-a",
                    "fallback_provider_ids": ["provider-c", "provider-b"],
                }
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["routing"]["general_chat"]["fallback_provider_ids"] == ["provider-c", "provider-b"]
    assert body["routing"]["general_chat"]["allow_runtime_override"] is True


def test_put_llm_settings_persists_runtime_override_flag(tmp_path, monkeypatch) -> None:
    settings_path = tmp_path / "ai-settings.json"
    monkeypatch.setenv("AI_SETTINGS_PATH", str(settings_path))

    client = create_client(tmp_path)
    response = client.put(
        "/api/llm-settings",
        json={
            "providers": [
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
                }
            ],
            "routing": {
                "general_chat": {
                    "primary_provider_id": "provider-a",
                    "fallback_provider_ids": [],
                    "allow_runtime_override": False,
                }
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["routing"]["general_chat"]["allow_runtime_override"] is False


def test_get_llm_settings_reports_stored_secret_status(tmp_path, monkeypatch) -> None:
    settings_path = tmp_path / "ai-settings.json"
    secrets_path = tmp_path / "llm-secrets.sqlite3"
    monkeypatch.setenv("AI_SETTINGS_PATH", str(settings_path))
    monkeypatch.setenv("LLM_SECRETS_DB_PATH", str(secrets_path))

    settings_path.write_text(
        json.dumps(
            {
                "llm_providers": [
                    {
                        "id": "provider-a",
                        "display_name": "Provider A",
                        "provider_type": "openrouter",
                        "auth_mode": "stored_secret",
                        "secret_ref": "OPENROUTER_API_KEY",
                        "base_url": "https://openrouter.ai/api/v1",
                        "model_id": "openai/gpt-4.1-mini",
                        "enabled": True,
                        "capabilities": ["chat"],
                        "context_window": 128000,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    from backend.ai_secret_store import SecretStore

    SecretStore(secrets_path).set_secret("OPENROUTER_API_KEY", "secret-value")

    client = create_client(tmp_path)
    response = client.get("/api/llm-settings")

    assert response.status_code == 200
    body = response.json()
    assert body["providers"][0]["has_stored_secret"] is True
    assert body["routing_purposes"] == [
        "general_chat",
        "agent",
        "document_analysis",
        "candidate_analysis",
        "job_matching",
    ]
    assert body["routing_labels"]["agent"] == "Agent"
    assert "workspace_files_write" in body["capability_model"]["job_finder_tool_capabilities"]


def test_put_llm_settings_rejects_invalid_payload_types(tmp_path, monkeypatch) -> None:
    settings_path = tmp_path / "ai-settings.json"
    monkeypatch.setenv("AI_SETTINGS_PATH", str(settings_path))

    client = create_client(tmp_path)
    response = client.put("/api/llm-settings", json={"providers": {}, "routing": {}})

    assert response.status_code == 400
    assert response.json()["detail"] == "llm_providers must be a list"


def test_put_llm_settings_returns_stored_secret_status(tmp_path, monkeypatch) -> None:
    settings_path = tmp_path / "ai-settings.json"
    secrets_path = tmp_path / "llm-secrets.sqlite3"
    monkeypatch.setenv("AI_SETTINGS_PATH", str(settings_path))
    monkeypatch.setenv("LLM_SECRETS_DB_PATH", str(secrets_path))

    from backend.ai_secret_store import SecretStore

    SecretStore(secrets_path).set_secret("OPENAI_API_KEY", "secret-value")

    client = create_client(tmp_path)
    response = client.put(
        "/api/llm-settings",
        json={
            "providers": [
                {
                    "id": "provider-openai",
                    "display_name": "OpenAI",
                    "provider_type": "openai",
                    "auth_mode": "stored_secret",
                    "secret_ref": "OPENAI_API_KEY",
                    "base_url": "https://api.openai.com/v1",
                    "model_id": "gpt-4.1-mini",
                    "enabled": True,
                    "capabilities": ["chat"],
                    "context_window": 128000,
                }
            ],
            "routing": {
                "general_chat": {
                    "primary_provider_id": "provider-openai",
                    "fallback_provider_ids": [],
                }
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["providers"][0]["has_stored_secret"] is True


def test_export_ai_settings_returns_portable_document(tmp_path, monkeypatch) -> None:
    settings_path = tmp_path / "ai-settings.json"
    monkeypatch.setenv("AI_SETTINGS_PATH", str(settings_path))

    client = create_client(tmp_path)
    response = client.get("/api/ai-settings/export")

    assert response.status_code == 200
    body = response.json()
    assert body["ai_settings"] == {"mutation_policy": "approve_writes"}
    assert body["llm_providers"][0]["id"] == "provider-default-ollama"
    assert "general_chat" in body["model_routing"]


def test_import_ai_settings_persists_valid_document(tmp_path, monkeypatch) -> None:
    settings_path = tmp_path / "ai-settings.json"
    monkeypatch.setenv("AI_SETTINGS_PATH", str(settings_path))

    client = create_client(tmp_path)
    document = {
        "ai_settings": {"mutation_policy": "read_only"},
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
            }
        ],
        "model_routing": {},
    }

    response = client.post("/api/ai-settings/import", json=document)

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["ai_settings"] == {"mutation_policy": "read_only"}
    assert body["providers"][0]["id"] == "provider-a"

    reload_response = client.get("/api/llm-settings")
    assert reload_response.json()["providers"][0]["id"] == "provider-a"


def test_import_ai_settings_rejects_invalid_document_without_changing_state(tmp_path, monkeypatch) -> None:
    settings_path = tmp_path / "ai-settings.json"
    monkeypatch.setenv("AI_SETTINGS_PATH", str(settings_path))

    client = create_client(tmp_path)
    before = client.get("/api/llm-settings").json()

    response = client.post(
        "/api/ai-settings/import",
        json={"llm_providers": [{"id": "provider-a"}], "model_routing": {}},
    )

    assert response.status_code == 400
    assert "missing required field" in response.json()["detail"]

    after = client.get("/api/llm-settings").json()
    assert after == before
