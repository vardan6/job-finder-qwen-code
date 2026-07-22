"""
Regression test for the manual add-job-title endpoint (Phase 9.5 —
preferred-title review reliability, review finding #4).

CandidateJobTitle has no mapped `created_at` column; the endpoint used to pass
created_at=func.now() into the constructor and always raised on an otherwise
valid request.
"""
from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.models.candidate import Candidate
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


def test_add_job_title_succeeds_for_a_valid_request(db):
    user = ensure_development_user(db)
    candidate = Candidate(name="Owner", user_id=user.id)
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    client = create_client(db)
    response = client.post(
        f"/candidates/{candidate.id}/job-titles",
        json={"title": "Staff SDET", "priority": 1},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
