"""
Tests for per-job tailored document generation (R11).

Mocks backend.services.llm_service.send_message and
backend.services.document_generation.resolve_chat_model_selection so no real
LLM or AI Settings configuration is required.
"""
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.models.candidate import Candidate
from backend.models.document import CandidateDocument, GeneratedDocument
from backend.models.job import Job
from backend.ownership import ensure_development_user, get_current_user
from backend.routes import jobs as jobs_routes
from backend.routes.jobs import router
from backend.services.ai_routing import RoutingSelection
from backend.services.document_generation import (
    DocumentGenerationError,
    generate_tailored_document,
    get_job_description_text,
)


def create_client(db) -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/jobs")

    def override_get_db() -> Iterator:
        yield db

    app.dependency_overrides[jobs_routes.get_db] = override_get_db
    app.dependency_overrides[jobs_routes.get_current_user] = lambda: ensure_development_user(db)
    return TestClient(app)


def make_candidate_with_resume(db, tmp_path, monkeypatch, content="# Alex Johnson\nStaff Backend Engineer with Python and AWS experience.") -> Candidate:
    # CandidateDocument.file_path is always resolved against DATA_DIR in
    # production; point DATA_DIR at tmp_path so the resume file resolves.
    monkeypatch.setattr("backend.services.document_generation.DATA_DIR", tmp_path)
    user = ensure_development_user(db)
    candidate = Candidate(name="Alex Johnson", user_id=user.id)
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    resume_path = tmp_path / "resume.md"
    resume_path.write_text(content, encoding="utf-8")
    db.add(
        CandidateDocument(
            candidate_id=candidate.id,
            filename="resume.md",
            file_path=str(resume_path),
            document_type="resume",
            parse_status="completed",
            is_active=True,
        )
    )
    db.commit()
    return candidate


def make_job(db, candidate: Candidate, description_snippet="Looking for a backend engineer with Python and AWS.") -> Job:
    job = Job(
        candidate_id=candidate.id,
        title="Senior Backend Engineer",
        company="Acme Corp",
        description_snippet=description_snippet,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


class FakeProvider:
    def __init__(self, name="openai"):
        self.name = name


class FakeModel:
    def __init__(self, model_name="gpt-test", provider=None):
        self.model_name = model_name
        self.provider = provider or FakeProvider()


def fake_selection(provider_name="openai", model_name="gpt-test"):
    model = FakeModel(model_name=model_name, provider=FakeProvider(provider_name))
    return RoutingSelection(provider=model.provider, model=model, source="test")


# ---------------------------------------------------------------------------
# Service-level tests
# ---------------------------------------------------------------------------

def test_get_job_description_text_falls_back_to_snippet():
    job = Job(candidate_id=1, title="T", company="C", description_snippet="A short snippet")
    assert get_job_description_text(job) == "A short snippet"


@pytest.mark.asyncio
async def test_generate_tailored_document_requires_resume(db, monkeypatch):
    user = ensure_development_user(db)
    candidate = Candidate(name="No Resume", user_id=user.id)
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    job = make_job(db, candidate)

    with pytest.raises(DocumentGenerationError, match="Upload a resume"):
        await generate_tailored_document(db, candidate, job, "resume")


@pytest.mark.asyncio
async def test_generate_tailored_document_persists_content_and_provenance(db, tmp_path, monkeypatch):
    candidate = make_candidate_with_resume(db, tmp_path, monkeypatch)
    job = make_job(db, candidate)

    captured_prompts = []

    async def fake_send_message(prompt, db=None, routing_purpose=None, **kwargs):
        captured_prompts.append((prompt, routing_purpose))
        return "Tailored resume content"

    monkeypatch.setattr("backend.services.document_generation.llm_service.send_message", fake_send_message)
    monkeypatch.setattr(
        "backend.services.document_generation.resolve_chat_model_selection",
        lambda db, purpose: fake_selection(),
    )

    generated = await generate_tailored_document(db, candidate, job, "resume")

    assert generated.content == "Tailored resume content"
    assert generated.document_type == "resume"
    assert generated.job_id == job.id
    assert generated.candidate_id == candidate.id
    assert generated.llm_provider_name == "openai"
    assert generated.llm_model_name == "gpt-test"
    assert captured_prompts[0][1] == "document_analysis"
    assert "Senior Backend Engineer" in captured_prompts[0][0]

    # Regenerating replaces the same row rather than creating a new one.
    async def fake_send_message_v2(prompt, db=None, routing_purpose=None, **kwargs):
        return "Regenerated resume content"

    monkeypatch.setattr("backend.services.document_generation.llm_service.send_message", fake_send_message_v2)
    regenerated = await generate_tailored_document(db, candidate, job, "resume")

    assert regenerated.id == generated.id
    assert regenerated.content == "Regenerated resume content"
    assert db.query(GeneratedDocument).filter(GeneratedDocument.job_id == job.id).count() == 1


@pytest.mark.asyncio
async def test_generate_tailored_document_raises_when_no_provider_configured(db, tmp_path, monkeypatch):
    candidate = make_candidate_with_resume(db, tmp_path, monkeypatch)
    job = make_job(db, candidate)

    def raise_not_configured(db, purpose):
        raise ValueError(f"No usable configured providers available for purpose '{purpose}'")

    monkeypatch.setattr(
        "backend.services.document_generation.resolve_chat_model_selection",
        raise_not_configured,
    )

    with pytest.raises(DocumentGenerationError, match="No LLM provider is configured"):
        await generate_tailored_document(db, candidate, job, "cover_letter")


@pytest.mark.asyncio
async def test_generate_tailored_document_raises_when_llm_returns_empty(db, tmp_path, monkeypatch):
    candidate = make_candidate_with_resume(db, tmp_path, monkeypatch)
    job = make_job(db, candidate)

    async def fake_send_message(*args, **kwargs):
        return None

    monkeypatch.setattr("backend.services.document_generation.llm_service.send_message", fake_send_message)
    monkeypatch.setattr(
        "backend.services.document_generation.resolve_chat_model_selection",
        lambda db, purpose: fake_selection(),
    )

    with pytest.raises(DocumentGenerationError, match="returned no content"):
        await generate_tailored_document(db, candidate, job, "cover_letter")


# ---------------------------------------------------------------------------
# Route-level tests
# ---------------------------------------------------------------------------

def test_generate_document_route_creates_and_returns_content(db, tmp_path, monkeypatch):
    candidate = make_candidate_with_resume(db, tmp_path, monkeypatch)
    job = make_job(db, candidate)

    async def fake_send_message(prompt, db=None, routing_purpose=None, **kwargs):
        return "Generated via route"

    monkeypatch.setattr("backend.services.document_generation.llm_service.send_message", fake_send_message)
    monkeypatch.setattr(
        "backend.services.document_generation.resolve_chat_model_selection",
        lambda db, purpose: fake_selection("ollama", "llama3"),
    )

    client = create_client(db)
    response = client.post(f"/jobs/{job.id}/generate-document/resume")

    assert response.status_code == 200
    assert "Generated via route" in response.text
    assert "ollama" in response.text

    generated = db.query(GeneratedDocument).filter(GeneratedDocument.job_id == job.id).first()
    assert generated is not None
    assert generated.content == "Generated via route"


def test_generate_document_route_returns_400_without_resume(db):
    user = ensure_development_user(db)
    candidate = Candidate(name="No Resume Here", user_id=user.id)
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    job = make_job(db, candidate)

    client = create_client(db)
    response = client.post(f"/jobs/{job.id}/generate-document/resume")

    assert response.status_code == 400
    assert "Upload a resume" in response.text


def test_generate_document_route_hides_jobs_owned_by_other_users(db, tmp_path):
    ensure_development_user(db)  # seeds the dev user first
    from backend.models.user import User

    stranger = User(email="stranger@local", display_name="Stranger")
    db.add(stranger)
    db.flush()
    foreign_candidate = Candidate(name="Foreign", user_id=stranger.id)
    db.add(foreign_candidate)
    db.commit()
    db.refresh(foreign_candidate)
    job = make_job(db, foreign_candidate)

    client = create_client(db)
    response = client.post(f"/jobs/{job.id}/generate-document/resume")

    assert response.status_code == 404


def test_download_generated_document_route(db, tmp_path, monkeypatch):
    candidate = make_candidate_with_resume(db, tmp_path, monkeypatch)
    job = make_job(db, candidate)

    async def fake_send_message(prompt, db=None, routing_purpose=None, **kwargs):
        return "Download me"

    monkeypatch.setattr("backend.services.document_generation.llm_service.send_message", fake_send_message)
    monkeypatch.setattr(
        "backend.services.document_generation.resolve_chat_model_selection",
        lambda db, purpose: fake_selection(),
    )

    client = create_client(db)
    generate_response = client.post(f"/jobs/{job.id}/generate-document/cover_letter")
    assert generate_response.status_code == 200

    download_response = client.get(f"/jobs/{job.id}/generated-document/cover_letter/download")
    assert download_response.status_code == 200
    assert download_response.text == "Download me"
    assert "attachment" in download_response.headers["content-disposition"]


def test_download_generated_document_route_404_when_missing(db, tmp_path, monkeypatch):
    candidate = make_candidate_with_resume(db, tmp_path, monkeypatch)
    job = make_job(db, candidate)

    client = create_client(db)
    response = client.get(f"/jobs/{job.id}/generated-document/resume/download")

    assert response.status_code == 404
