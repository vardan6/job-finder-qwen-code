"""
Cross-profile access denial tests for job-title routes (Phase 9.5 —
title-route profile isolation).

candidate_parser.py routes previously loaded candidates by id alone, with no
check that the candidate belonged to the requesting principal. These tests
confirm every read/write route now 404s when the candidate belongs to a
different user.
"""
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.models.candidate import Candidate
from backend.models.document import CandidateDocument
from backend.models.supporting import CandidateJobTitle
from backend.models.user import User
from backend.ownership import ensure_development_user
from backend.routes import candidate_parser as candidate_parser_routes
from backend.routes.candidate_parser import router


def create_client(db) -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/candidates")

    def override_get_db() -> Iterator:
        yield db

    app.dependency_overrides[candidate_parser_routes.get_db] = override_get_db
    app.dependency_overrides[candidate_parser_routes.get_current_user] = (
        lambda: ensure_development_user(db)
    )
    return TestClient(app)


@pytest.fixture
def foreign_candidate(db) -> Candidate:
    stranger = User(email="stranger@local", display_name="Stranger")
    db.add(stranger)
    db.flush()
    candidate = Candidate(name="Foreign", user_id=stranger.id)
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


@pytest.fixture
def foreign_job_title(db, foreign_candidate) -> CandidateJobTitle:
    title = CandidateJobTitle(candidate_id=foreign_candidate.id, title="Foreign Title", priority=2)
    db.add(title)
    db.commit()
    db.refresh(title)
    return title


def test_get_documents_denies_foreign_candidate(db, foreign_candidate):
    client = create_client(db)
    response = client.get(f"/candidates/{foreign_candidate.id}/documents")
    assert response.status_code == 404


def test_parse_job_titles_denies_foreign_candidate(db, foreign_candidate):
    client = create_client(db)
    response = client.post(f"/candidates/{foreign_candidate.id}/parse-job-titles", json={})
    assert response.status_code == 404


def test_save_job_titles_denies_foreign_candidate(db, foreign_candidate):
    client = create_client(db)
    response = client.post(
        f"/candidates/{foreign_candidate.id}/save-job-titles",
        json={"job_titles": [{"title": "Engineer"}]},
    )
    assert response.status_code == 404


def test_save_parsed_job_titles_persists_and_returns_the_reviewed_title(db):
    """The browser sends source ids and original values from the review table.

    Saving that exact payload must create a preferred title that a subsequent
    page load can render; otherwise a successful parse appears to have done
    nothing, as it did before the review-save path was repaired.
    """
    user = ensure_development_user(db)
    candidate = Candidate(name="Owner", user_id=user.id)
    db.add(candidate)
    db.flush()
    document = CandidateDocument(
        candidate_id=candidate.id,
        filename="resume.md",
        file_path="resume.md",
        document_type="resume",
    )
    db.add(document)
    db.commit()

    client = create_client(db)
    save_response = client.post(
        f"/candidates/{candidate.id}/save-job-titles",
        json={
            "job_titles": [{
                "title": "Staff Software Engineer",
                "original_extracted_title": "Staff Software Engineer",
                "priority": 1,
                "description": "Most recent target role",
                "source_document_id": document.id,
            }],
            "source_document_ids": [document.id],
        },
    )

    assert save_response.status_code == 200
    assert save_response.json()["outcome"]["created"] == 1

    titles_response = client.get(f"/candidates/{candidate.id}/job-titles")

    assert titles_response.status_code == 200
    assert titles_response.json()["job_titles"] == [{
        "id": 1,
        "title": "Staff Software Engineer",
        "priority": 1,
        "description": "Most recent target role",
        "source": "extracted",
        "original_extracted_value": "Staff Software Engineer",
        "source_file": "resume.md",
    }]


def test_get_job_titles_denies_foreign_candidate(db, foreign_candidate):
    client = create_client(db)
    response = client.get(f"/candidates/{foreign_candidate.id}/job-titles")
    assert response.status_code == 404


def test_add_job_title_denies_foreign_candidate(db, foreign_candidate):
    client = create_client(db)
    response = client.post(
        f"/candidates/{foreign_candidate.id}/job-titles",
        json={"title": "Engineer"},
    )
    assert response.status_code == 404


def test_bulk_save_job_titles_denies_foreign_candidate(db, foreign_candidate):
    client = create_client(db)
    response = client.put(
        f"/candidates/{foreign_candidate.id}/job-titles/bulk-save",
        json={"job_titles": [{"title": "Engineer"}]},
    )
    assert response.status_code == 404


def test_delete_job_title_denies_foreign_candidate(db, foreign_candidate, foreign_job_title):
    client = create_client(db)
    response = client.delete(
        f"/candidates/{foreign_candidate.id}/job-titles/{foreign_job_title.id}"
    )
    assert response.status_code == 404


def test_update_job_title_denies_foreign_candidate(db, foreign_candidate, foreign_job_title):
    client = create_client(db)
    response = client.put(
        f"/candidates/{foreign_candidate.id}/job-titles/{foreign_job_title.id}",
        json={"title": "Changed"},
    )
    assert response.status_code == 404


def test_reset_job_title_denies_foreign_candidate(db, foreign_candidate, foreign_job_title):
    client = create_client(db)
    response = client.post(
        f"/candidates/{foreign_candidate.id}/job-titles/{foreign_job_title.id}/reset-to-extracted"
    )
    assert response.status_code == 404
