from __future__ import annotations
from collections.abc import Iterator
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.ai_session_store import get_ai_session_store
from backend.models.candidate import Candidate
from backend.models.document import CandidateDocument
from backend.models.llm_provider import LLMModel, LLMProvider
from backend.models.supporting import CandidateJobTitle, CandidatePreferences, CandidateSkill
from backend.routes import chat as chat_routes
from backend.routes.chat import router


def create_client(db) -> TestClient:
    app = FastAPI()
    app.include_router(router)

    def override_get_db() -> Iterator:
        yield db

    app.dependency_overrides[chat_routes.get_db] = override_get_db
    return TestClient(app)


def create_model(db) -> LLMModel:
    provider = LLMProvider(name="openai", api_url="https://example.test/v1", is_active=True)
    db.add(provider)
    db.flush()
    model = LLMModel(
        provider_id=provider.id,
        model_name="gpt-test",
        display_name="GPT Test",
        is_active=True,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


def write_ai_settings(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def read_stream_events(response) -> list[dict]:
    payload = "".join(response.iter_text())
    events: list[dict] = []
    for raw_event in payload.split("\n\n"):
        raw_event = raw_event.strip()
        if not raw_event or not raw_event.startswith("data: "):
            continue
        events.append(json.loads(raw_event[6:]))
    return events


def fake_completion_response(
    content: str,
    *,
    usage: dict | None = None,
    response_metadata: dict | None = None,
):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=usage or {},
        response_metadata=response_metadata or {},
    )


def test_chat_creates_and_persists_session(tmp_path, monkeypatch, db) -> None:
    monkeypatch.setenv("AI_SESSIONS_DB_PATH", str(tmp_path / "ai-sessions.sqlite3"))
    model = create_model(db)

    async def fake_completion(timeout_seconds, **kwargs):
        assert timeout_seconds > 0
        assert kwargs["messages"][-1]["content"] == "Help me tailor my resume"
        return fake_completion_response(
            "Start with the impact bullets.",
            usage={"prompt_tokens": 120, "completion_tokens": 24, "total_tokens": 144},
        )

    def fake_build_completion_kwargs(provider, selected_model, messages):
        return {"messages": messages, "provider": provider.name, "model": selected_model.model_name}

    monkeypatch.setattr("backend.services.llm_service._async_completion_response", fake_completion)
    monkeypatch.setattr("backend.services.llm_service._build_completion_kwargs", fake_build_completion_kwargs)

    client = create_client(db)
    response = client.post(
        "/api/chat",
        data={"model_id": str(model.id), "message": "Help me tailor my resume"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["session_id"].startswith("ai-session-")
    assert payload["session"]["title"].startswith("Help me tailor my resume")
    assert payload["conversation"] == [
        {"role": "user", "content": "Help me tailor my resume"},
        {"role": "assistant", "content": "Start with the impact bullets."},
    ]

    session = get_ai_session_store().get_session(payload["session_id"])
    assert session is not None
    assert [message["role"] for message in session["messages"]] == ["user", "assistant"]
    assert session["messages"][1]["meta"]["provider"] == "openai"
    assert session["messages"][1]["meta"]["tokens_used"] == 144
    assert session["meta"]["selected_model_id"] == model.id
    assert payload["session"]["attached_candidate_id"] is None
    assert payload["session"]["attached_candidate_name"] == ""
    assert payload["meta"]["tokens_used"] == 144
    assert payload["meta"]["usage_metadata"]["prompt_tokens"] == 120
    assert payload["meta"]["usage_metadata"]["completion_tokens"] == 24


def test_chat_reuses_persisted_session_history(tmp_path, monkeypatch, db) -> None:
    monkeypatch.setenv("AI_SESSIONS_DB_PATH", str(tmp_path / "ai-sessions.sqlite3"))
    model = create_model(db)
    call_count = {"count": 0}
    captured_messages: list[list[dict[str, str]]] = []

    async def fake_completion(timeout_seconds, **kwargs):
        call_count["count"] += 1
        captured_messages.append(kwargs["messages"])
        return fake_completion_response("First reply" if call_count["count"] == 1 else "Second reply")

    def fake_build_completion_kwargs(provider, selected_model, messages):
        return {"messages": messages, "provider": provider.name, "model": selected_model.model_name}

    monkeypatch.setattr("backend.services.llm_service._async_completion_response", fake_completion)
    monkeypatch.setattr("backend.services.llm_service._build_completion_kwargs", fake_build_completion_kwargs)

    client = create_client(db)
    first = client.post("/api/chat", data={"model_id": str(model.id), "message": "First question"})
    session_id = first.json()["session_id"]

    second = client.post(
        "/api/chat",
        data={"model_id": str(model.id), "message": "Second question", "session_id": session_id},
    )

    assert second.status_code == 200
    assert captured_messages[-1] == [
        {"role": "user", "content": "First question"},
        {"role": "assistant", "content": "First reply"},
        {"role": "user", "content": "Second question"},
    ]

    session = get_ai_session_store().get_session(session_id)
    assert session is not None
    assert len(session["messages"]) == 4
    assert second.json()["conversation"][-1] == {"role": "assistant", "content": "Second reply"}


def test_chat_uses_model_routing_when_model_id_missing(tmp_path, monkeypatch, db) -> None:
    monkeypatch.setenv("AI_SESSIONS_DB_PATH", str(tmp_path / "ai-sessions.sqlite3"))
    settings_path = tmp_path / "ai-settings.json"
    monkeypatch.setenv("AI_SETTINGS_PATH", str(settings_path))

    openai = LLMProvider(name="openai", api_url="https://openai.example/v1", is_active=True)
    anthropic = LLMProvider(name="anthropic", api_url="https://anthropic.example/v1", is_active=True)
    db.add_all([openai, anthropic])
    db.flush()
    openai_model = LLMModel(provider_id=openai.id, model_name="gpt-test", display_name="GPT Test", is_active=True)
    anthropic_model = LLMModel(provider_id=anthropic.id, model_name="claude-test", display_name="Claude Test", is_active=True)
    db.add_all([openai_model, anthropic_model])
    db.commit()

    write_ai_settings(
        settings_path,
        {
                "llm_providers": [
                    {"id": "provider-openai", "display_name": "OpenAI", "provider_type": "openai", "auth_mode": "none", "model_id": "gpt-test", "enabled": True, "capabilities": ["chat"]},
                    {"id": "provider-anthropic", "display_name": "Claude Test", "provider_type": "anthropic", "auth_mode": "none", "model_id": "claude-test", "enabled": True, "capabilities": ["chat"]},
            ],
            "model_routing": {
                "general_chat": {
                    "primary_provider_id": "provider-anthropic",
                    "fallback_provider_ids": ["provider-openai"],
                }
            },
        },
    )

    async def fake_completion(timeout_seconds, **kwargs):
        assert timeout_seconds > 0
        return fake_completion_response("Routed response")

    def fake_build_completion_kwargs(provider, selected_model, messages):
        return {"messages": messages, "provider": provider.name, "model": selected_model.model_name}

    monkeypatch.setattr("backend.services.llm_service._async_completion_response", fake_completion)
    monkeypatch.setattr("backend.services.llm_service._build_completion_kwargs", fake_build_completion_kwargs)

    client = create_client(db)
    response = client.post("/api/chat", data={"message": "Route this"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["meta"]["provider"] == "Claude Test"
    assert payload["meta"]["model"] == "claude-test"


def test_chat_uses_agent_routing_for_agent_mode(tmp_path, monkeypatch, db) -> None:
    monkeypatch.setenv("AI_SESSIONS_DB_PATH", str(tmp_path / "ai-sessions.sqlite3"))
    settings_path = tmp_path / "ai-settings.json"
    monkeypatch.setenv("AI_SETTINGS_PATH", str(settings_path))

    openai = LLMProvider(name="openai", api_url="https://openai.example/v1", is_active=True)
    anthropic = LLMProvider(name="anthropic", api_url="https://anthropic.example/v1", is_active=True)
    db.add_all([openai, anthropic])
    db.flush()
    openai_model = LLMModel(provider_id=openai.id, model_name="gpt-test", display_name="GPT Test", is_active=True)
    anthropic_model = LLMModel(provider_id=anthropic.id, model_name="claude-test", display_name="Claude Test", is_active=True)
    db.add_all([openai_model, anthropic_model])
    db.commit()

    write_ai_settings(
        settings_path,
        {
                "llm_providers": [
                    {"id": "provider-openai", "display_name": "OpenAI", "provider_type": "openai", "auth_mode": "none", "model_id": "gpt-test", "enabled": True, "capabilities": ["chat"]},
                    {"id": "provider-anthropic", "display_name": "Claude Test", "provider_type": "anthropic", "auth_mode": "none", "model_id": "claude-test", "enabled": True, "capabilities": ["chat"]},
            ],
            "model_routing": {
                "general_chat": {
                    "primary_provider_id": "provider-openai",
                    "fallback_provider_ids": ["provider-anthropic"],
                },
                "agent": {
                    "primary_provider_id": "provider-anthropic",
                    "fallback_provider_ids": ["provider-openai"],
                },
            },
        },
    )

    async def fake_completion(timeout_seconds, **kwargs):
        assert timeout_seconds > 0
        return fake_completion_response("Agent routed response")

    def fake_build_completion_kwargs(provider, selected_model, messages):
        return {"messages": messages, "provider": provider.name, "model": selected_model.model_name}

    monkeypatch.setattr("backend.services.llm_service._async_completion_response", fake_completion)
    monkeypatch.setattr("backend.services.llm_service._build_completion_kwargs", fake_build_completion_kwargs)

    client = create_client(db)
    response = client.post("/api/chat", data={"mode": "agent", "message": "Route this in agent mode"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["provider"] == "Claude Test"
    assert payload["session"]["mode"] == "agent"


def test_chat_explicit_model_id_overrides_routing_primary(tmp_path, monkeypatch, db) -> None:
    monkeypatch.setenv("AI_SESSIONS_DB_PATH", str(tmp_path / "ai-sessions.sqlite3"))
    settings_path = tmp_path / "ai-settings.json"
    monkeypatch.setenv("AI_SETTINGS_PATH", str(settings_path))

    openai = LLMProvider(name="openai", api_url="https://openai.example/v1", is_active=True)
    anthropic = LLMProvider(name="anthropic", api_url="https://anthropic.example/v1", is_active=True)
    db.add_all([openai, anthropic])
    db.flush()
    openai_model = LLMModel(provider_id=openai.id, model_name="gpt-test", display_name="GPT Test", is_active=True)
    anthropic_model = LLMModel(provider_id=anthropic.id, model_name="claude-test", display_name="Claude Test", is_active=True)
    db.add_all([openai_model, anthropic_model])
    db.commit()

    write_ai_settings(
        settings_path,
        {
                "llm_providers": [
                    {"id": "provider-openai", "display_name": "OpenAI", "provider_type": "openai", "auth_mode": "none", "model_id": "gpt-test", "enabled": True, "capabilities": ["chat"]},
                    {"id": "provider-anthropic", "display_name": "Claude Test", "provider_type": "anthropic", "auth_mode": "none", "model_id": "claude-test", "enabled": True, "capabilities": ["chat"]},
            ],
            "model_routing": {
                "general_chat": {
                    "primary_provider_id": "provider-anthropic",
                    "fallback_provider_ids": ["provider-openai"],
                }
            },
        },
    )

    async def fake_completion(timeout_seconds, **kwargs):
        assert timeout_seconds > 0
        assert kwargs["provider"] == "openai"
        assert kwargs["model"] == "gpt-test"
        return fake_completion_response("Explicit override")

    def fake_build_completion_kwargs(provider, selected_model, messages):
        return {"messages": messages, "provider": provider.name, "model": selected_model.model_name}

    monkeypatch.setattr("backend.services.llm_service._async_completion_response", fake_completion)
    monkeypatch.setattr("backend.services.llm_service._build_completion_kwargs", fake_build_completion_kwargs)

    client = create_client(db)
    response = client.post("/api/chat", data={"model_id": str(openai_model.id), "message": "Use explicit model"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["meta"]["provider"] == "OpenAI"
    assert payload["meta"]["model"] == "gpt-test"


def test_chat_rejects_invalid_mode(tmp_path, monkeypatch, db) -> None:
    monkeypatch.setenv("AI_SESSIONS_DB_PATH", str(tmp_path / "ai-sessions.sqlite3"))
    model = create_model(db)

    client = create_client(db)
    response = client.post(
        "/api/chat",
        data={"model_id": str(model.id), "mode": "bad_mode", "message": "Use explicit model"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "mode must be one of: general_chat, agent"


def test_chat_rejects_explicit_model_override_when_disabled(tmp_path, monkeypatch, db) -> None:
    monkeypatch.setenv("AI_SESSIONS_DB_PATH", str(tmp_path / "ai-sessions.sqlite3"))
    settings_path = tmp_path / "ai-settings.json"
    monkeypatch.setenv("AI_SETTINGS_PATH", str(settings_path))

    openai = LLMProvider(name="openai", api_url="https://openai.example/v1", is_active=True)
    anthropic = LLMProvider(name="anthropic", api_url="https://anthropic.example/v1", is_active=True)
    db.add_all([openai, anthropic])
    db.flush()
    openai_model = LLMModel(provider_id=openai.id, model_name="gpt-test", display_name="GPT Test", is_active=True)
    anthropic_model = LLMModel(provider_id=anthropic.id, model_name="claude-test", display_name="Claude Test", is_active=True)
    db.add_all([openai_model, anthropic_model])
    db.commit()

    write_ai_settings(
        settings_path,
        {
            "llm_providers": [
                {"id": "provider-openai", "provider_type": "openai", "model_id": "gpt-test", "enabled": True, "capabilities": ["chat"]},
                {"id": "provider-anthropic", "provider_type": "anthropic", "model_id": "claude-test", "enabled": True, "capabilities": ["chat"]},
            ],
            "model_routing": {
                "general_chat": {
                    "primary_provider_id": "provider-anthropic",
                    "fallback_provider_ids": ["provider-openai"],
                    "allow_runtime_override": False,
                }
            },
        },
    )

    client = create_client(db)
    response = client.post("/api/chat", data={"model_id": str(openai_model.id), "message": "Use explicit model"})

    assert response.status_code == 400
    assert "Runtime model override is disabled" in response.json()["detail"]


def test_chat_stream_persists_final_assistant_message(tmp_path, monkeypatch, db) -> None:
    monkeypatch.setenv("AI_SESSIONS_DB_PATH", str(tmp_path / "ai-sessions.sqlite3"))
    model = create_model(db)

    async def fake_stream_completion(**kwargs):
        assert kwargs["stream"] is True
        assert kwargs["messages"][-1]["content"] == "Stream this reply"
        assert kwargs["stream_options"] == {"include_usage": True}

        async def iterator():
            yield {"choices": [{"delta": {"content": "Hello"}}]}
            yield {
                "choices": [{"delta": {"content": " world"}}],
                "usage": {"prompt_tokens": 16, "completion_tokens": 4, "total_tokens": 20},
            }

        return iterator()

    def fake_build_completion_kwargs(provider, selected_model, messages):
        return {"messages": messages, "provider": provider.name, "model": selected_model.model_name}

    monkeypatch.setattr("litellm.acompletion", fake_stream_completion)
    monkeypatch.setattr("backend.services.llm_service._build_completion_kwargs", fake_build_completion_kwargs)

    client = create_client(db)
    with client.stream(
        "POST",
        "/api/chat/stream",
        data={"model_id": str(model.id), "message": "Stream this reply"},
    ) as response:
        assert response.status_code == 200
        events = read_stream_events(response)

    assert [event["type"] for event in events] == ["session", "chunk", "chunk", "done"]
    assert events[0]["session"]["title"].startswith("Stream this reply")
    assert events[1]["delta"] == "Hello"
    assert events[2]["delta"] == " world"
    assert events[-1]["message"] == "Hello world"
    assert events[-1]["meta"]["tokens_used"] == 20
    assert events[-1]["meta"]["usage_metadata"]["prompt_tokens"] == 16
    assert events[-1]["meta"]["usage_metadata"]["completion_tokens"] == 4
    assert events[-1]["conversation"] == [
        {"role": "user", "content": "Stream this reply"},
        {"role": "assistant", "content": "Hello world"},
    ]
    assert events[-1]["diagnostics"]["run_mode"] == "general_chat"
    assert "retrieval" in events[-1]["diagnostics"]

    session_id = events[0]["session_id"]
    session = get_ai_session_store().get_session(session_id)
    assert session is not None
    assert [message["role"] for message in session["messages"]] == ["user", "assistant"]
    assert session["messages"][-1]["content"] == "Hello world"
    assert session["messages"][-1]["meta"]["tokens_used"] == 20


def test_chat_stream_routing_falls_back_when_primary_missing(tmp_path, monkeypatch, db) -> None:
    monkeypatch.setenv("AI_SESSIONS_DB_PATH", str(tmp_path / "ai-sessions.sqlite3"))
    settings_path = tmp_path / "ai-settings.json"
    monkeypatch.setenv("AI_SETTINGS_PATH", str(settings_path))

    openai = LLMProvider(name="openai", api_url="https://openai.example/v1", is_active=True)
    db.add(openai)
    db.flush()
    openai_model = LLMModel(provider_id=openai.id, model_name="gpt-test", display_name="GPT Test", is_active=True)
    db.add(openai_model)
    db.commit()

    write_ai_settings(
        settings_path,
        {
                "llm_providers": [
                    {"id": "provider-openai", "display_name": "OpenAI", "provider_type": "openai", "auth_mode": "none", "model_id": "gpt-test", "enabled": True, "capabilities": ["chat"]},
                    {"id": "provider-missing", "display_name": "Anthropic", "provider_type": "anthropic", "auth_mode": "stored_secret", "secret_ref": "ANTHROPIC_API_KEY", "model_id": "claude-test", "enabled": True, "capabilities": ["chat"]},
            ],
            "model_routing": {
                "general_chat": {
                    "primary_provider_id": "provider-missing",
                    "fallback_provider_ids": ["provider-openai"],
                }
            },
        },
    )

    async def fake_stream_completion(**kwargs):
        assert kwargs["stream"] is True
        assert kwargs["provider"] == "openai"
        assert kwargs["model"] == "gpt-test"

        async def iterator():
            yield {"choices": [{"delta": {"content": "Fallback"}}]}

        return iterator()

    def fake_build_completion_kwargs(provider, selected_model, messages):
        return {"messages": messages, "provider": provider.name, "model": selected_model.model_name}

    monkeypatch.setattr("litellm.acompletion", fake_stream_completion)
    monkeypatch.setattr("backend.services.llm_service._build_completion_kwargs", fake_build_completion_kwargs)

    client = create_client(db)
    with client.stream(
        "POST",
        "/api/chat/stream",
        data={"message": "Fallback route"},
    ) as response:
        assert response.status_code == 200
        events = read_stream_events(response)

    assert events[-1]["type"] == "done"
    assert events[-1]["meta"]["provider"] == "OpenAI"
    assert events[-1]["message"] == "Fallback"


def test_chat_rejects_unresolvable_routing_config(tmp_path, monkeypatch, db) -> None:
    monkeypatch.setenv("AI_SESSIONS_DB_PATH", str(tmp_path / "ai-sessions.sqlite3"))
    settings_path = tmp_path / "ai-settings.json"
    monkeypatch.setenv("AI_SETTINGS_PATH", str(settings_path))

    # No anthropic provider/model exists in DB, but routing points only to anthropic.
    write_ai_settings(
        settings_path,
        {
            "llm_providers": [
                {"id": "provider-missing", "display_name": "Anthropic", "provider_type": "anthropic", "auth_mode": "stored_secret", "secret_ref": "ANTHROPIC_API_KEY", "model_id": "claude-test", "enabled": True, "capabilities": ["chat"]},
            ],
            "model_routing": {
                "general_chat": {
                    "primary_provider_id": "provider-missing",
                    "fallback_provider_ids": [],
                }
            },
        },
    )

    client = create_client(db)
    response = client.post("/api/chat", data={"message": "Route this"})

    assert response.status_code == 400
    assert "No usable configured providers available for purpose 'general_chat'" == response.json()["detail"]


def test_chat_uses_stored_secret_configured_provider_without_db_runtime_row(tmp_path, monkeypatch, db) -> None:
    monkeypatch.setenv("AI_SESSIONS_DB_PATH", str(tmp_path / "ai-sessions.sqlite3"))
    monkeypatch.setenv("AI_SETTINGS_PATH", str(tmp_path / "ai-settings.json"))
    monkeypatch.setenv("LLM_SECRETS_DB_PATH", str(tmp_path / "llm-secrets.sqlite3"))

    write_ai_settings(
        tmp_path / "ai-settings.json",
        {
            "llm_providers": [
                {
                    "id": "provider-openai",
                    "display_name": "OpenAI",
                    "provider_type": "openai",
                    "auth_mode": "stored_secret",
                    "secret_ref": "OPENAI_API_KEY",
                    "base_url": "https://api.openai.com/v1",
                    "model_id": "gpt-5.4-nano",
                    "enabled": True,
                    "capabilities": ["chat", "tools"],
                }
            ],
            "model_routing": {
                "general_chat": {
                    "primary_provider_id": "provider-openai",
                    "fallback_provider_ids": [],
                    "allow_runtime_override": True,
                }
            },
        },
    )

    from backend.ai_secret_store import SecretStore

    SecretStore(tmp_path / "llm-secrets.sqlite3").set_secret("OPENAI_API_KEY", "secret-value")

    async def fake_completion(timeout_seconds, **kwargs):
        assert timeout_seconds > 0
        assert kwargs["model"] == "openai/gpt-5.4-nano"
        assert kwargs["api_base"] == "https://api.openai.com/v1"
        assert kwargs["api_key"] == "secret-value"
        return fake_completion_response("Stored secret route works")

    monkeypatch.setattr("backend.services.llm_service._async_completion_response", fake_completion)

    client = create_client(db)
    response = client.post("/api/chat", data={"message": "Use configured provider"})

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Stored secret route works"
    assert body["meta"]["provider"] == "OpenAI"
    assert body["session"]["meta"]["selected_provider_config_id"] == "provider-openai"


def test_chat_falls_back_when_requested_provider_has_no_secret(tmp_path, monkeypatch, db) -> None:
    monkeypatch.setenv("AI_SESSIONS_DB_PATH", str(tmp_path / "ai-sessions.sqlite3"))
    monkeypatch.setenv("AI_SETTINGS_PATH", str(tmp_path / "ai-settings.json"))
    monkeypatch.setenv("LLM_SECRETS_DB_PATH", str(tmp_path / "llm-secrets.sqlite3"))

    write_ai_settings(
        tmp_path / "ai-settings.json",
        {
            "llm_providers": [
                {
                    "id": "provider-openai",
                    "display_name": "OpenAI",
                    "provider_type": "openai",
                    "auth_mode": "stored_secret",
                    "secret_ref": "OPENAI_API_KEY",
                    "base_url": "https://api.openai.com/v1",
                    "model_id": "gpt-5.4-nano",
                    "enabled": True,
                    "capabilities": ["chat", "tools"],
                },
                {
                    "id": "provider-groq",
                    "display_name": "Groq",
                    "provider_type": "groq",
                    "auth_mode": "env_var",
                    "secret_ref": "GROQ_API_KEY",
                    "base_url": "https://api.groq.com/openai/v1",
                    "model_id": "openai/gpt-oss-120b",
                    "enabled": True,
                    "capabilities": ["chat"],
                },
            ],
            "model_routing": {
                "general_chat": {
                    "primary_provider_id": "provider-openai",
                    "fallback_provider_ids": ["provider-groq"],
                    "allow_runtime_override": True,
                }
            },
        },
    )
    monkeypatch.setenv("GROQ_API_KEY", "groq-secret")

    async def fake_completion(timeout_seconds, **kwargs):
        assert timeout_seconds > 0
        assert kwargs["model"] == "openai/gpt-oss-120b"
        assert kwargs["api_key"] == "groq-secret"
        return fake_completion_response("Fallback route works")

    monkeypatch.setattr("backend.services.llm_service._async_completion_response", fake_completion)

    client = create_client(db)
    response = client.post(
        "/api/chat",
        data={"message": "Fallback please", "selected_provider_config_id": "provider-openai"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Fallback route works"
    assert body["meta"]["provider"] == "Groq"
    assert body["meta"]["fallback_used"] is True
    assert body["meta"]["selection_source"] == "routing_fallback_from_explicit_provider"
    assert body["meta"]["requested_provider_config_id"] == "provider-openai"
    assert body["meta"]["requested_provider_name"] == "OpenAI"
    assert body["meta"]["resolved_provider_config_id"] == "provider-groq"
    assert body["meta"]["resolved_provider_name"] == "Groq"
    assert body["session"]["meta"]["selected_provider_config_id"] == "provider-groq"


def test_chat_stream_explicit_model_id_overrides_routing_primary(tmp_path, monkeypatch, db) -> None:
    monkeypatch.setenv("AI_SESSIONS_DB_PATH", str(tmp_path / "ai-sessions.sqlite3"))
    settings_path = tmp_path / "ai-settings.json"
    monkeypatch.setenv("AI_SETTINGS_PATH", str(settings_path))

    openai = LLMProvider(name="openai", api_url="https://openai.example/v1", is_active=True)
    anthropic = LLMProvider(name="anthropic", api_url="https://anthropic.example/v1", is_active=True)
    db.add_all([openai, anthropic])
    db.flush()
    openai_model = LLMModel(provider_id=openai.id, model_name="gpt-test", display_name="GPT Test", is_active=True)
    anthropic_model = LLMModel(provider_id=anthropic.id, model_name="claude-test", display_name="Claude Test", is_active=True)
    db.add_all([openai_model, anthropic_model])
    db.commit()

    write_ai_settings(
        settings_path,
        {
                "llm_providers": [
                    {"id": "provider-openai", "display_name": "OpenAI", "provider_type": "openai", "auth_mode": "none", "model_id": "gpt-test", "enabled": True, "capabilities": ["chat"]},
                    {"id": "provider-anthropic", "display_name": "Claude Test", "provider_type": "anthropic", "auth_mode": "none", "model_id": "claude-test", "enabled": True, "capabilities": ["chat"]},
            ],
            "model_routing": {
                "general_chat": {
                    "primary_provider_id": "provider-anthropic",
                    "fallback_provider_ids": ["provider-openai"],
                }
            },
        },
    )

    async def fake_stream_completion(**kwargs):
        assert kwargs["stream"] is True
        assert kwargs["provider"] == "openai"
        assert kwargs["model"] == "gpt-test"

        async def iterator():
            yield {"choices": [{"delta": {"content": "Explicit stream"}}]}

        return iterator()

    def fake_build_completion_kwargs(provider, selected_model, messages):
        return {"messages": messages, "provider": provider.name, "model": selected_model.model_name}

    monkeypatch.setattr("litellm.acompletion", fake_stream_completion)
    monkeypatch.setattr("backend.services.llm_service._build_completion_kwargs", fake_build_completion_kwargs)

    client = create_client(db)
    with client.stream(
        "POST",
        "/api/chat/stream",
        data={"model_id": str(openai_model.id), "message": "Use explicit stream model"},
    ) as response:
        assert response.status_code == 200
        events = read_stream_events(response)

    assert events[-1]["type"] == "done"
    assert events[-1]["meta"]["provider"] == "OpenAI"
    assert events[-1]["meta"]["model"] == "gpt-test"
    assert events[-1]["message"] == "Explicit stream"


def test_chat_stream_explicit_model_id_falls_back_to_db_provider_when_config_match_lacks_credentials(
    tmp_path,
    monkeypatch,
    db,
) -> None:
    monkeypatch.setenv("AI_SESSIONS_DB_PATH", str(tmp_path / "ai-sessions.sqlite3"))
    settings_path = tmp_path / "ai-settings.json"
    monkeypatch.setenv("AI_SETTINGS_PATH", str(settings_path))
    monkeypatch.setenv("LLM_SECRETS_DB_PATH", str(tmp_path / "llm-secrets.sqlite3"))

    openai = LLMProvider(name="openai", api_url="https://db-openai.example/v1", is_active=True)
    db.add(openai)
    db.flush()
    openai_model = LLMModel(provider_id=openai.id, model_name="gpt-test", display_name="GPT Test", is_active=True)
    db.add(openai_model)
    db.commit()

    write_ai_settings(
        settings_path,
        {
            "llm_providers": [
                {
                    "id": "provider-openai",
                    "display_name": "OpenAI",
                    "provider_type": "openai",
                    "auth_mode": "stored_secret",
                    "secret_ref": "MISSING_OPENAI_API_KEY",
                    "base_url": "https://api.openai.com/v1",
                    "model_id": "gpt-test",
                    "enabled": True,
                    "capabilities": ["chat"],
                }
            ],
            "model_routing": {
                "general_chat": {
                    "primary_provider_id": "provider-openai",
                    "fallback_provider_ids": [],
                }
            },
        },
    )

    async def fake_stream_completion(**kwargs):
        assert kwargs["stream"] is True
        assert kwargs["provider"] == "openai"
        assert kwargs["model"] == "gpt-test"

        async def iterator():
            yield {"choices": [{"delta": {"content": "DB route still works"}}]}

        return iterator()

    def fake_build_completion_kwargs(provider, selected_model, messages):
        assert provider.api_url == "https://db-openai.example/v1"
        assert not hasattr(provider, "api_key")
        return {"messages": messages, "provider": provider.name, "model": selected_model.model_name}

    monkeypatch.setattr("litellm.acompletion", fake_stream_completion)
    monkeypatch.setattr("backend.services.llm_service._build_completion_kwargs", fake_build_completion_kwargs)

    client = create_client(db)
    with client.stream(
        "POST",
        "/api/chat/stream",
        data={"model_id": str(openai_model.id), "message": "Use the DB model"},
    ) as response:
        assert response.status_code == 200
        events = read_stream_events(response)

    assert events[-1]["type"] == "done"
    assert events[-1]["message"] == "DB route still works"
    assert events[-1]["meta"]["selection_source"] == "explicit_model"


def test_chat_stream_emits_trace_and_tool_activity_in_agent_mode(tmp_path, monkeypatch, db) -> None:
    monkeypatch.setenv("AI_SESSIONS_DB_PATH", str(tmp_path / "ai-sessions.sqlite3"))
    model = create_model(db)

    async def fake_stream_completion(**kwargs):
        assert kwargs["stream"] is True

        async def iterator():
            yield {"choices": [{"delta": {"content": "Agent reply"}}]}

        return iterator()

    def fake_build_completion_kwargs(provider, selected_model, messages):
        return {"messages": messages, "provider": provider.name, "model": selected_model.model_name}

    monkeypatch.setattr("litellm.acompletion", fake_stream_completion)
    monkeypatch.setattr("backend.services.llm_service._build_completion_kwargs", fake_build_completion_kwargs)

    client = create_client(db)
    with client.stream(
        "POST",
        "/api/chat/stream",
        data={"model_id": str(model.id), "mode": "agent", "message": "Run in agent mode"},
    ) as response:
        assert response.status_code == 200
        events = read_stream_events(response)

    event_types = [event["type"] for event in events]
    assert "trace" in event_types
    assert "tool_activity" in event_types
    assert event_types[-1] == "done"


def test_chat_stream_agent_mode_plan_command_emits_interaction_required(tmp_path, monkeypatch, db) -> None:
    monkeypatch.setenv("AI_SESSIONS_DB_PATH", str(tmp_path / "ai-sessions.sqlite3"))
    model = create_model(db)

    async def fake_stream_completion(**kwargs):
        raise AssertionError("LLM stream should not be called for local /plan interaction flow")

    monkeypatch.setattr("litellm.acompletion", fake_stream_completion)

    client = create_client(db)
    with client.stream(
        "POST",
        "/api/chat/stream",
        data={"model_id": str(model.id), "mode": "agent", "message": "/plan draft a strategy"},
    ) as response:
        assert response.status_code == 200
        events = read_stream_events(response)

    assert [event["type"] for event in events] == ["session", "trace", "tool_activity", "interaction_required"]
    interaction = events[-1]["interaction"]
    assert interaction["kind"] == "clarification"
    assert interaction["title"] == "Plan clarification needed"


def test_chat_stream_rejects_explicit_model_override_when_disabled(tmp_path, monkeypatch, db) -> None:
    monkeypatch.setenv("AI_SESSIONS_DB_PATH", str(tmp_path / "ai-sessions.sqlite3"))
    settings_path = tmp_path / "ai-settings.json"
    monkeypatch.setenv("AI_SETTINGS_PATH", str(settings_path))

    openai = LLMProvider(name="openai", api_url="https://openai.example/v1", is_active=True)
    anthropic = LLMProvider(name="anthropic", api_url="https://anthropic.example/v1", is_active=True)
    db.add_all([openai, anthropic])
    db.flush()
    openai_model = LLMModel(provider_id=openai.id, model_name="gpt-test", display_name="GPT Test", is_active=True)
    anthropic_model = LLMModel(provider_id=anthropic.id, model_name="claude-test", display_name="Claude Test", is_active=True)
    db.add_all([openai_model, anthropic_model])
    db.commit()

    write_ai_settings(
        settings_path,
        {
            "llm_providers": [
                {"id": "provider-openai", "provider_type": "openai", "model_id": "gpt-test", "enabled": True, "capabilities": ["chat"]},
                {"id": "provider-anthropic", "provider_type": "anthropic", "model_id": "claude-test", "enabled": True, "capabilities": ["chat"]},
            ],
            "model_routing": {
                "general_chat": {
                    "primary_provider_id": "provider-anthropic",
                    "fallback_provider_ids": ["provider-openai"],
                    "allow_runtime_override": False,
                }
            },
        },
    )

    client = create_client(db)
    response = client.post(
        "/api/chat/stream",
        data={"model_id": str(openai_model.id), "message": "Use explicit stream model"},
    )
    assert response.status_code == 400
    assert "Runtime model override is disabled" in response.json()["detail"]


def test_chat_stream_timeout_returns_error_event(tmp_path, monkeypatch, db) -> None:
    monkeypatch.setenv("AI_SESSIONS_DB_PATH", str(tmp_path / "ai-sessions.sqlite3"))
    model = create_model(db)

    async def fake_stream_completion(**kwargs):
        raise TimeoutError()

    def fake_build_completion_kwargs(provider, selected_model, messages):
        return {"messages": messages, "provider": provider.name, "model": selected_model.model_name}

    monkeypatch.setattr("litellm.acompletion", fake_stream_completion)
    monkeypatch.setattr("backend.services.llm_service._build_completion_kwargs", fake_build_completion_kwargs)

    client = create_client(db)
    with client.stream(
        "POST",
        "/api/chat/stream",
        data={"model_id": str(model.id), "message": "Timeout please"},
    ) as response:
        assert response.status_code == 200
        events = read_stream_events(response)

    assert [event["type"] for event in events] == ["session", "error"]
    assert events[-1]["message"].startswith("LLM did not respond within ")
    assert events[-1]["message"].endswith("Check that your provider is running and try again.")


@pytest.mark.asyncio
async def test_chat_stream_disconnect_does_not_persist_orphaned_user_turn(tmp_path, monkeypatch, db) -> None:
    monkeypatch.setenv("AI_SESSIONS_DB_PATH", str(tmp_path / "ai-sessions.sqlite3"))
    model = create_model(db)
    close_calls = {"count": 0}

    async def fake_stream_completion(**kwargs):
        assert kwargs["stream"] is True

        class FakeStream:
            def __init__(self) -> None:
                self._chunks = iter(
                    [
                        {"choices": [{"delta": {"content": "Partial"}}]},
                        {"choices": [{"delta": {"content": " reply"}}]},
                    ]
                )

            async def __anext__(self):
                try:
                    return next(self._chunks)
                except StopIteration as exc:
                    raise StopAsyncIteration() from exc

            async def aclose(self):
                close_calls["count"] += 1

        return FakeStream()

    def fake_build_completion_kwargs(provider, selected_model, messages):
        return {"messages": messages, "provider": provider.name, "model": selected_model.model_name}

    class FakeRequest:
        def __init__(self) -> None:
            self.calls = 0

        async def is_disconnected(self) -> bool:
            self.calls += 1
            return self.calls > 1

    monkeypatch.setattr("litellm.acompletion", fake_stream_completion)
    monkeypatch.setattr("backend.services.llm_service._build_completion_kwargs", fake_build_completion_kwargs)

    response = await chat_routes.chat_stream(
        request=FakeRequest(),
        model_id=model.id,
        selected_provider_config_id="",
        mode="general_chat",
        message="Stop mid-stream",
        session_id="",
        conversation_history="[]",
        db=db,
    )

    events: list[dict] = []
    async for raw_event in response.body_iterator:
        text = raw_event.decode("utf-8") if isinstance(raw_event, bytes) else str(raw_event)
        for block in text.split("\n\n"):
            block = block.strip()
            if block.startswith("data: "):
                events.append(json.loads(block[6:]))

    assert [event["type"] for event in events] == ["session", "chunk"]
    session_id = events[0]["session_id"]
    assert get_ai_session_store().get_session(session_id) is None
    assert close_calls["count"] == 1


def test_chat_stream_reuses_existing_persisted_session(tmp_path, monkeypatch, db) -> None:
    monkeypatch.setenv("AI_SESSIONS_DB_PATH", str(tmp_path / "ai-sessions.sqlite3"))
    model = create_model(db)
    replies = iter([
        [{"choices": [{"delta": {"content": "First"}}]}],
        [{"choices": [{"delta": {"content": "Second"}}]}],
    ])
    captured_messages: list[list[dict[str, str]]] = []

    async def fake_stream_completion(**kwargs):
        captured_messages.append(kwargs["messages"])
        chunks = next(replies)

        async def iterator():
            for chunk in chunks:
                yield chunk

        return iterator()

    def fake_build_completion_kwargs(provider, selected_model, messages):
        return {"messages": messages, "provider": provider.name, "model": selected_model.model_name}

    monkeypatch.setattr("litellm.acompletion", fake_stream_completion)
    monkeypatch.setattr("backend.services.llm_service._build_completion_kwargs", fake_build_completion_kwargs)

    client = create_client(db)
    with client.stream(
        "POST",
        "/api/chat/stream",
        data={"model_id": str(model.id), "message": "First prompt"},
    ) as response:
        first_events = read_stream_events(response)

    session_id = first_events[0]["session_id"]

    with client.stream(
        "POST",
        "/api/chat/stream",
        data={"model_id": str(model.id), "message": "Second prompt", "session_id": session_id},
    ) as response:
        second_events = read_stream_events(response)

    assert captured_messages[-1] == [
        {"role": "user", "content": "First prompt"},
        {"role": "assistant", "content": "First"},
        {"role": "user", "content": "Second prompt"},
    ]
    assert second_events[-1]["conversation"] == [
        {"role": "user", "content": "First prompt"},
        {"role": "assistant", "content": "First"},
        {"role": "user", "content": "Second prompt"},
        {"role": "assistant", "content": "Second"},
    ]


def test_chat_includes_attached_candidate_context_when_enabled(tmp_path, monkeypatch, db) -> None:
    monkeypatch.setenv("AI_SESSIONS_DB_PATH", str(tmp_path / "ai-sessions.sqlite3"))
    model = create_model(db)

    candidate = Candidate(
        name="Alex Johnson",
        current_role="Staff Backend Engineer",
        location="United States",
        timezone="America/New_York",
        experience_years=9,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    db.add(CandidateJobTitle(candidate_id=candidate.id, title="Principal Software Engineer", priority=1, is_active=True))
    db.add(CandidateSkill(candidate_id=candidate.id, skill_name="Python", is_enabled=True, is_active=True))
    db.add(
        CandidateDocument(
            candidate_id=candidate.id,
            filename="resume.md",
            file_path="candidates/alex/resume.md",
            document_type="resume",
            parse_status="completed",
            is_active=True,
        )
    )
    db.add(
        CandidatePreferences(
            candidate_id=candidate.id,
            min_score=75,
            min_ai_remote_score=85,
            remote_only=True,
            experience_levels='["Staff","Principal"]',
        )
    )
    db.commit()

    store = get_ai_session_store()
    session = store.create_session(
        source_controls={
            "candidate_profile": True,
            "candidate_job_titles": True,
            "candidate_skills": True,
            "candidate_documents": True,
            "job_preferences": True,
            "ai_chat_history": False,
            "settings_config": False,
            "workspace_files": False,
        },
        meta={
            "attached_candidate_id": candidate.id,
            "attached_candidate_name": candidate.name,
        },
    )

    captured_messages: list[list[dict[str, str]]] = []

    async def fake_completion(timeout_seconds, **kwargs):
        captured_messages.append(kwargs["messages"])
        return fake_completion_response("Context received.")

    def fake_build_completion_kwargs(provider, selected_model, messages):
        return {"messages": messages, "provider": provider.name, "model": selected_model.model_name}

    monkeypatch.setattr("backend.services.llm_service._async_completion_response", fake_completion)
    monkeypatch.setattr("backend.services.llm_service._build_completion_kwargs", fake_build_completion_kwargs)

    client = create_client(db)
    response = client.post(
        "/api/chat",
        data={"model_id": str(model.id), "message": "Summarize my profile", "session_id": session["id"]},
    )

    assert response.status_code == 200
    system_message = captured_messages[-1][0]
    assert system_message["role"] == "system"
    assert "Attached candidate ID" in system_message["content"]
    assert "Alex Johnson" in system_message["content"]
    assert "Principal Software Engineer" in system_message["content"]
    assert "Python" in system_message["content"]
    assert "resume.md" in system_message["content"]
    assert "Remote only: yes" in system_message["content"]
    assert captured_messages[-1][-1] == {"role": "user", "content": "Summarize my profile"}


def test_chat_skips_candidate_context_without_attachment(tmp_path, monkeypatch, db) -> None:
    monkeypatch.setenv("AI_SESSIONS_DB_PATH", str(tmp_path / "ai-sessions.sqlite3"))
    model = create_model(db)
    store = get_ai_session_store()
    session = store.create_session(
        source_controls={
            "candidate_profile": True,
            "candidate_job_titles": True,
            "candidate_skills": True,
            "candidate_documents": True,
            "job_preferences": True,
            "ai_chat_history": False,
            "settings_config": False,
            "workspace_files": False,
        },
    )

    captured_messages: list[list[dict[str, str]]] = []

    async def fake_completion(timeout_seconds, **kwargs):
        captured_messages.append(kwargs["messages"])
        return fake_completion_response("No candidate context.")

    def fake_build_completion_kwargs(provider, selected_model, messages):
        return {"messages": messages, "provider": provider.name, "model": selected_model.model_name}

    monkeypatch.setattr("backend.services.llm_service._async_completion_response", fake_completion)
    monkeypatch.setattr("backend.services.llm_service._build_completion_kwargs", fake_build_completion_kwargs)

    client = create_client(db)
    response = client.post(
        "/api/chat",
        data={"model_id": str(model.id), "message": "Hello", "session_id": session["id"]},
    )

    assert response.status_code == 200
    assert captured_messages[-1] == [{"role": "user", "content": "Hello"}]


def test_chat_page_lists_active_candidates(tmp_path, monkeypatch, db) -> None:
    monkeypatch.setenv("AI_SESSIONS_DB_PATH", str(tmp_path / "ai-sessions.sqlite3"))
    create_model(db)
    active_candidate = Candidate(name="Alex Johnson", location="United States", timezone="America/New_York")
    inactive_candidate = Candidate(
        name="Archived Person",
        location="United States",
        timezone="America/New_York",
        is_active=False,
    )
    db.add_all([active_candidate, inactive_candidate])
    db.commit()

    client = create_client(db)
    response = client.get("/chat")

    assert response.status_code == 200
    assert '/static/css/chat.css' in response.text
    assert 'Press Enter to send' in response.text
    assert 'option value="%s">Alex Johnson' % active_candidate.id in response.text
    assert "Archived Person" not in response.text


def test_chat_page_lists_configured_llm_providers_from_ai_settings(tmp_path, monkeypatch, db) -> None:
    monkeypatch.setenv("AI_SESSIONS_DB_PATH", str(tmp_path / "ai-sessions.sqlite3"))
    monkeypatch.setenv("AI_SETTINGS_PATH", str(tmp_path / "ai-settings.json"))
    create_model(db)

    write_ai_settings(
        tmp_path / "ai-settings.json",
        {
            "llm_providers": [
                {
                    "id": "provider-openrouter",
                    "display_name": "OpenRouter Claude Sonnet",
                    "provider_type": "openrouter",
                    "model_id": "anthropic/claude-sonnet-4.5",
                    "enabled": True,
                    "capabilities": ["chat", "tools"],
                },
                {
                    "id": "provider-groq",
                    "display_name": "Groq",
                    "provider_type": "groq",
                    "model_id": "openai/gpt-oss-120b",
                    "enabled": True,
                    "capabilities": ["chat"],
                },
                {
                    "id": "provider-disabled",
                    "display_name": "Disabled Provider",
                    "provider_type": "openai",
                    "model_id": "gpt-disabled",
                    "enabled": False,
                    "capabilities": ["chat"],
                },
            ],
            "model_routing": {
                "general_chat": {
                    "primary_provider_id": "provider-openrouter",
                    "fallback_provider_ids": ["provider-groq"],
                    "allow_runtime_override": True,
                }
            },
        },
    )

    client = create_client(db)
    response = client.get("/chat")

    assert response.status_code == 200
    assert 'value="provider-openrouter"' in response.text
    assert 'OpenRouter Claude Sonnet · anthropic/claude-sonnet-4.5' in response.text
    assert 'value="provider-groq"' in response.text
    assert 'Groq · openai/gpt-oss-120b' in response.text
    assert 'Disabled Provider' not in response.text
