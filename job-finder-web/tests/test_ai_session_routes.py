from __future__ import annotations

from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.models.candidate import Candidate
from backend.routes import ai_sessions as ai_sessions_routes
from backend.routes.ai_sessions import router


def create_client(db) -> TestClient:
    app = FastAPI()
    app.include_router(router)

    def override_get_db() -> Iterator:
        yield db

    app.dependency_overrides[ai_sessions_routes.get_db] = override_get_db
    return TestClient(app)


def test_create_and_get_ai_session(tmp_path, monkeypatch, db) -> None:
    monkeypatch.setenv("AI_SESSIONS_DB_PATH", str(tmp_path / "ai-sessions.sqlite3"))

    client = create_client(db)
    create_response = client.post("/api/ai/sessions", json={"title": "Resume helper"})

    assert create_response.status_code == 201
    session = create_response.json()["session"]
    assert session["title"] == "Resume helper"
    assert session["mode"] == "general_chat"

    get_response = client.get(f"/api/ai/sessions/{session['id']}")

    assert get_response.status_code == 200
    assert get_response.json()["session"]["id"] == session["id"]


def test_update_archive_restore_and_purge_ai_session(tmp_path, monkeypatch, db) -> None:
    monkeypatch.setenv("AI_SESSIONS_DB_PATH", str(tmp_path / "ai-sessions.sqlite3"))

    candidate = Candidate(name="Taylor Swift", location="United States", timezone="America/New_York")
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    client = create_client(db)
    session = client.post("/api/ai/sessions", json={}).json()["session"]

    update_response = client.patch(
        f"/api/ai/sessions/{session['id']}",
        json={
            "provider_id": "provider-a",
            "source_controls": {"ai_chat_history": True},
            "attached_candidate_id": candidate.id,
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["session"]["provider_id"] == "provider-a"
    assert update_response.json()["session"]["source_controls"]["ai_chat_history"] is True
    assert update_response.json()["session"]["source_controls"]["candidate_profile"] is True
    assert update_response.json()["session"]["source_controls"]["job_preferences"] is False
    assert update_response.json()["session"]["meta"]["attached_candidate_id"] == candidate.id
    assert update_response.json()["session"]["meta"]["attached_candidate_name"] == candidate.name

    archive_response = client.post(f"/api/ai/sessions/{session['id']}/archive")
    assert archive_response.status_code == 200
    assert archive_response.json()["session"]["archived_at"] is not None

    restore_response = client.post(f"/api/ai/sessions/{session['id']}/restore")
    assert restore_response.status_code == 200
    assert restore_response.json()["session"]["archived_at"] is None

    purge_response = client.delete(f"/api/ai/sessions/{session['id']}")
    assert purge_response.status_code == 200
    assert purge_response.json() == {"ok": True}


def test_list_messages_and_search_matches(tmp_path, monkeypatch, db) -> None:
    monkeypatch.setenv("AI_SESSIONS_DB_PATH", str(tmp_path / "ai-sessions.sqlite3"))

    from backend.ai_session_store import get_ai_session_store

    store = get_ai_session_store()
    session = store.create_session(title="Searchable")
    store.add_message(session["id"], role="user", content="Summarize my resume")
    store.add_message(session["id"], role="assistant", content="Your resume emphasizes backend systems")

    client = create_client(db)
    messages_response = client.get(f"/api/ai/sessions/{session['id']}/messages")
    search_response = client.get("/api/ai/messages/search", params={"query": "resume"})

    assert messages_response.status_code == 200
    assert len(messages_response.json()["messages"]) == 2
    assert search_response.status_code == 200
    assert search_response.json()["matches"][0]["session_id"] == session["id"]


def test_update_ai_session_rejects_missing_candidate(tmp_path, monkeypatch, db) -> None:
    monkeypatch.setenv("AI_SESSIONS_DB_PATH", str(tmp_path / "ai-sessions.sqlite3"))

    client = create_client(db)
    session = client.post("/api/ai/sessions", json={}).json()["session"]

    response = client.patch(
        f"/api/ai/sessions/{session['id']}",
        json={"attached_candidate_id": 999999},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Candidate not found"


def test_create_ai_session_rejects_invalid_mode(tmp_path, monkeypatch, db) -> None:
    monkeypatch.setenv("AI_SESSIONS_DB_PATH", str(tmp_path / "ai-sessions.sqlite3"))

    client = create_client(db)
    response = client.post("/api/ai/sessions", json={"mode": "legacy_rover_mode"})

    assert response.status_code == 400
    assert response.json()["detail"] == "mode must be one of: general_chat, agent"
