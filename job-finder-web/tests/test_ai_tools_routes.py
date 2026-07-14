from __future__ import annotations

import json
from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.ai_session_store import get_ai_session_store
from backend.models.candidate import Candidate
from backend.models.document import CandidateDocument
from backend.models.job import Job, JobApplication
from backend.models.supporting import CandidateJobTitle, CandidateSkill
from backend.routes import ai_tools as ai_tools_routes
from backend.routes.ai_tools import router


def create_client(db) -> TestClient:
    app = FastAPI()
    app.include_router(router)

    def override_get_db() -> Iterator:
        yield db

    app.dependency_overrides[ai_tools_routes.get_db] = override_get_db
    return TestClient(app)


def test_list_tools_contains_expected_surfaces(db) -> None:
    client = create_client(db)
    response = client.get("/api/ai/tools")

    assert response.status_code == 200
    tools = response.json()["tools"]
    names = {item["name"] for item in tools}
    assert "candidate_profile_lookup" in names
    assert "candidate_jobs_lookup" in names
    assert "candidate_employers_lookup" in names
    assert "candidate_applications_lookup" in names
    assert "chat_history_lookup" in names
    assert "workspace_files_write" in names


def test_execute_candidate_lookups_and_chat_history(tmp_path, monkeypatch, db) -> None:
    monkeypatch.setenv("AI_SESSIONS_DB_PATH", str(tmp_path / "ai-sessions.sqlite3"))

    candidate = Candidate(name="Casey", email="casey@example.com", current_role="Backend Engineer")
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    db.add(CandidateJobTitle(candidate_id=candidate.id, title="Senior Backend Engineer", priority=1))
    db.add(CandidateSkill(candidate_id=candidate.id, skill_name="Python", category="required", years_experience=8))
    db.add(
        CandidateDocument(
            candidate_id=candidate.id,
            filename="resume.md",
            file_path="candidates/casey/resume.md",
            document_type="resume",
            parse_status="completed",
            load_strategy="immediate",
        )
    )
    db.commit()

    store = get_ai_session_store()
    session = store.create_session(title="Lookup test")
    store.add_message(session["id"], role="user", content="Hello")

    client = create_client(db)

    profile_response = client.post(
        "/api/ai/tools/execute",
        json={"tool": "candidate_profile_lookup", "args": {"candidate_id": candidate.id}},
    )
    assert profile_response.status_code == 200
    assert profile_response.json()["result"]["candidate"]["name"] == "Casey"

    titles_response = client.post(
        "/api/ai/tools/execute",
        json={"tool": "candidate_titles_lookup", "args": {"candidate_id": candidate.id}},
    )
    assert titles_response.status_code == 200
    assert titles_response.json()["result"]["titles"][0]["title"] == "Senior Backend Engineer"

    chat_response = client.post(
        "/api/ai/tools/execute",
        json={"tool": "chat_history_lookup", "args": {"session_id": session["id"], "limit": 10}},
    )
    assert chat_response.status_code == 200
    assert chat_response.json()["result"]["messages"][0]["content"] == "Hello"


def test_workspace_read_and_write_policy_gating(tmp_path, monkeypatch, db) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("AI_WORKSPACE_ROOT", str(workspace))
    monkeypatch.setenv("AI_SETTINGS_PATH", str(tmp_path / "ai-settings.json"))

    source_file = workspace / "notes.txt"
    source_file.write_text("hello", encoding="utf-8")

    client = create_client(db)

    read_response = client.post(
        "/api/ai/tools/execute",
        json={"tool": "workspace_files_read", "args": {"path": "notes.txt"}},
    )
    assert read_response.status_code == 200
    assert read_response.json()["result"]["content"] == "hello"

    blocked_write = client.post(
        "/api/ai/tools/execute",
        json={"tool": "workspace_files_write", "args": {"path": "out.txt", "content": "data"}},
    )
    assert blocked_write.status_code == 409
    assert blocked_write.json()["approval_required"] is True

    blocked_by_policy = client.post(
        "/api/ai/tools/execute",
        json={
            "tool": "workspace_files_write",
            "args": {"path": "out.txt", "content": "data"},
            "approval": {"state": "approved"},
        },
    )
    assert blocked_by_policy.status_code == 403

    settings_path = tmp_path / "ai-settings.json"
    settings_path.write_text(json.dumps({"ai_settings": {"mutation_policy": "allow_writes"}}), encoding="utf-8")

    allowed_write = client.post(
        "/api/ai/tools/execute",
        json={
            "tool": "workspace_files_write",
            "args": {"path": "folder/out.txt", "content": "data", "create_dirs": True},
            "approval": {"state": "approved"},
        },
    )
    assert allowed_write.status_code == 200
    assert (workspace / "folder" / "out.txt").read_text(encoding="utf-8") == "data"


def test_workspace_write_approval_object_must_be_dict(tmp_path, monkeypatch, db) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("AI_WORKSPACE_ROOT", str(workspace))
    monkeypatch.setenv("AI_SETTINGS_PATH", str(tmp_path / "ai-settings.json"))
    (tmp_path / "ai-settings.json").write_text(
        json.dumps({"ai_settings": {"mutation_policy": "allow_writes"}}),
        encoding="utf-8",
    )

    client = create_client(db)
    response = client.post(
        "/api/ai/tools/execute",
        json={
            "tool": "workspace_files_write",
            "args": {"path": "bad.txt", "content": "x"},
            "approval": "approved",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "approval must be an object"


def test_candidate_jobs_lookup_supports_status_and_limit(db) -> None:
    candidate = Candidate(name="Jordan", email="jordan@example.com", current_role="Engineer")
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    db.add(Job(candidate_id=candidate.id, title="Backend Engineer", company="Acme", status="active", platform="linkedin"))
    db.add(Job(candidate_id=candidate.id, title="Platform Engineer", company="Beta", status="applied", platform="glassdoor"))
    db.commit()

    client = create_client(db)
    all_jobs_response = client.post(
        "/api/ai/tools/execute",
        json={"tool": "candidate_jobs_lookup", "args": {"candidate_id": candidate.id}},
    )
    assert all_jobs_response.status_code == 200
    all_jobs = all_jobs_response.json()["result"]["jobs"]
    assert len(all_jobs) == 2

    active_only_response = client.post(
        "/api/ai/tools/execute",
        json={"tool": "candidate_jobs_lookup", "args": {"candidate_id": candidate.id, "status": "active", "limit": 1}},
    )
    assert active_only_response.status_code == 200
    active_only = active_only_response.json()["result"]
    assert active_only["count"] == 1
    assert active_only["jobs"][0]["status"] == "active"


def test_candidate_employers_lookup_aggregates_company_context(db) -> None:
    candidate = Candidate(name="Taylor", email="taylor@example.com", current_role="Engineer")
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    db.add(Job(candidate_id=candidate.id, title="SWE II", company="Acme", status="active", platform="linkedin"))
    db.add(Job(candidate_id=candidate.id, title="SWE III", company="Acme", status="applied", platform="glassdoor"))
    db.add(Job(candidate_id=candidate.id, title="Platform Engineer", company="Beta", status="active", platform="linkedin"))
    db.commit()

    client = create_client(db)
    response = client.post(
        "/api/ai/tools/execute",
        json={"tool": "candidate_employers_lookup", "args": {"candidate_id": candidate.id, "limit": 10}},
    )
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["count"] == 2
    assert result["employers"][0]["company"] == "Acme"
    assert result["employers"][0]["job_count"] == 2
    assert sorted(result["employers"][0]["platforms"]) == ["glassdoor", "linkedin"]


def test_candidate_applications_lookup_supports_status_and_limit(db) -> None:
    candidate = Candidate(name="Morgan", email="morgan@example.com", current_role="Engineer")
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    job_1 = Job(candidate_id=candidate.id, title="SWE II", company="Acme", status="active", platform="linkedin")
    job_2 = Job(candidate_id=candidate.id, title="Platform Engineer", company="Beta", status="active", platform="greenhouse")
    db.add(job_1)
    db.add(job_2)
    db.commit()
    db.refresh(job_1)
    db.refresh(job_2)

    db.add(JobApplication(job_id=job_1.id, status="applied", notes="Resume sent"))
    db.add(JobApplication(job_id=job_2.id, status="interview", notes="Phone screen scheduled"))
    db.commit()

    client = create_client(db)
    response = client.post(
        "/api/ai/tools/execute",
        json={"tool": "candidate_applications_lookup", "args": {"candidate_id": candidate.id, "limit": 5}},
    )
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["count"] == 2
    assert {item["status"] for item in result["applications"]} == {"applied", "interview"}

    filtered_response = client.post(
        "/api/ai/tools/execute",
        json={
            "tool": "candidate_applications_lookup",
            "args": {"candidate_id": candidate.id, "status": "interview", "limit": 5},
        },
    )
    assert filtered_response.status_code == 200
    filtered = filtered_response.json()["result"]
    assert filtered["count"] == 1
    assert filtered["applications"][0]["status"] == "interview"


def test_lookup_limit_validation_returns_400_for_invalid_values(db) -> None:
    candidate = Candidate(name="Skyler", email="skyler@example.com", current_role="Engineer")
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    client = create_client(db)
    for tool in ("candidate_jobs_lookup", "candidate_employers_lookup", "candidate_applications_lookup", "chat_history_lookup"):
        args = {"candidate_id": candidate.id, "limit": "bad"}
        if tool == "chat_history_lookup":
            session = get_ai_session_store().create_session(title="limits")
            args = {"session_id": session["id"], "limit": "bad"}
        response = client.post("/api/ai/tools/execute", json={"tool": tool, "args": args})
        assert response.status_code == 400
        assert response.json()["detail"] == "limit must be an integer"
