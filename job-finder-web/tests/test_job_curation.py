"""R7 result curation keeps saved-list snapshots immutable and exportable."""
from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.database import get_db
from backend.models.candidate import Candidate
from backend.models.job import Job, SearchRun, SearchRunJob
from backend.routes import jobs as jobs_routes
from backend.routes.jobs import router


def _client(db) -> TestClient:
    app = FastAPI()
    app.include_router(router)

    def override_get_db() -> Iterator:
        yield db

    app.dependency_overrides[jobs_routes.get_db] = override_get_db
    return TestClient(app)


def _saved_list(db):
    candidate = Candidate(name="Casey", folder_path="/tmp/curation")
    db.add(candidate)
    db.flush()
    remote = Job(candidate_id=candidate.id, title="Remote role", company="Acme", status="active", location="Anywhere")
    low_score = Job(candidate_id=candidate.id, title="Low score role", company="Beta", status="active")
    db.add_all([remote, low_score])
    db.flush()
    search_run = SearchRun(candidate_id=candidate.id, name="Backend search", query="Backend", platforms='["linkedin"]')
    db.add(search_run)
    db.flush()
    db.add_all([
        SearchRunJob(search_run_id=search_run.id, job_id=remote.id, first_sighting=True,
                     sighted_platforms='["linkedin"]', deterministic_score=93, salary="$150k",
                     verified_remote_status="fully_remote"),
        SearchRunJob(search_run_id=search_run.id, job_id=low_score.id, first_sighting=True,
                     sighted_platforms='["linkedin"]', deterministic_score=35,
                     verified_remote_status="hybrid"),
    ])
    db.commit()
    return search_run, remote, low_score


def test_saved_list_curation_filters_snapshots_and_exports_visible_rows(db):
    search_run, remote, low_score = _saved_list(db)
    client = _client(db)

    filtered = client.get(f"/lists/{search_run.id}?min_score=80&verified_remote_only=true")
    assert filtered.status_code == 200
    assert "Remote role" in filtered.text
    assert "Low score role" not in filtered.text

    export = client.get(f"/lists/{search_run.id}/export?min_score=80&verified_remote_only=true")
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("text/csv")
    assert "Remote role" in export.text
    assert "Low score role" not in export.text
    assert "$150k" in export.text


def test_dismissal_hides_job_but_keeps_it_in_saved_history(db):
    search_run, remote, _ = _saved_list(db)
    client = _client(db)

    response = client.post(f"/{remote.id}/dismiss", follow_redirects=False)
    assert response.status_code == 303
    assert db.get(Job, remote.id).is_dismissed is True

    hidden = client.get(f"/lists/{search_run.id}")
    assert "Remote role" not in hidden.text
    visible = client.get(f"/lists/{search_run.id}?include_dismissed=true")
    assert "Remote role" in visible.text
    assert "Dismissed" in visible.text
