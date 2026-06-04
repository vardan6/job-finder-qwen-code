from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routes.ai_secrets import router


def create_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_put_and_get_secret_status(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LLM_SECRETS_DB_PATH", str(tmp_path / "llm-secrets.sqlite3"))

    client = create_client()
    put_response = client.put("/api/llm-secrets/OPENROUTER_API_KEY", json={"secret_value": "secret-value"})

    assert put_response.status_code == 200
    assert put_response.json() == {
        "ok": True,
        "secret_ref": "OPENROUTER_API_KEY",
        "has_secret": True,
    }

    get_response = client.get("/api/llm-secrets/OPENROUTER_API_KEY")

    assert get_response.status_code == 200
    assert get_response.json() == {
        "secret_ref": "OPENROUTER_API_KEY",
        "has_secret": True,
    }


def test_delete_secret_status(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LLM_SECRETS_DB_PATH", str(tmp_path / "llm-secrets.sqlite3"))

    client = create_client()
    client.put("/api/llm-secrets/OPENROUTER_API_KEY", json={"secret_value": "secret-value"})

    delete_response = client.delete("/api/llm-secrets/OPENROUTER_API_KEY")

    assert delete_response.status_code == 200
    assert delete_response.json() == {
        "ok": True,
        "secret_ref": "OPENROUTER_API_KEY",
        "has_secret": False,
    }


def test_put_secret_requires_value(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LLM_SECRETS_DB_PATH", str(tmp_path / "llm-secrets.sqlite3"))

    client = create_client()
    response = client.put("/api/llm-secrets/OPENROUTER_API_KEY", json={"secret_value": ""})

    assert response.status_code == 400
    assert response.json()["detail"] == "secret_value is required"
