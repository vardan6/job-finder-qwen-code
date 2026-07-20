from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.database import get_db
from backend.models.candidate import Candidate
from backend.models.job import Job
from backend.routes import jobs as jobs_routes
from backend.routes.jobs import router


def create_client(db) -> TestClient:
    app = FastAPI()
    app.include_router(router)

    def override_get_db() -> Iterator:
        yield db

    app.dependency_overrides[jobs_routes.get_db] = override_get_db
    return TestClient(app)


def test_results_table_defaults_to_best_match_and_exposes_result_details(db) -> None:
    candidate = Candidate(name="Casey", email="casey@example.com")
    db.add(candidate)
    db.flush()
    db.add_all([
        Job(
            candidate_id=candidate.id, title="Lower match", company="Beta", status="active",
            deterministic_score=42, salary="$90k–$110k", verified_remote_status="hybrid",
            score_breakdown='{"title_similarity": 50, "skills_overlap": 0.3, "skills_status": "matched"}',
        ),
        Job(
            candidate_id=candidate.id, title="Best match", company="Acme", status="active",
            deterministic_score=91, salary="$140k–$170k", verified_remote_status="fully_remote",
            score_breakdown='{"title_similarity": 95, "skills_overlap": 0.85, "skills_status": "matched"}',
        ),
    ])
    db.commit()

    response = create_client(db).get("/")

    assert response.status_code == 200
    assert response.text.index("Best match") < response.text.index("Lower match")
    assert "Salary" in response.text
    assert "$140k–$170k" in response.text
    assert "Verified remote" in response.text
    assert "Fully remote" in response.text
    assert "Title similarity" in response.text
    assert "sort=score" in response.text


def test_results_table_accepts_a_sortable_column(db) -> None:
    candidate = Candidate(name="Casey", email="casey@example.com")
    db.add(candidate)
    db.flush()
    db.add_all([
        Job(candidate_id=candidate.id, title="Zulu", company="Acme", status="active", deterministic_score=99),
        Job(candidate_id=candidate.id, title="Alpha", company="Beta", status="active", deterministic_score=1),
    ])
    db.commit()

    response = create_client(db).get("/?sort=title&direction=asc")

    assert response.status_code == 200
    assert response.text.index("Alpha") < response.text.index("Zulu")
    assert "Sorted by title." in response.text
