"""R11 application pipeline: per-job status tracking via JobApplication."""
from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.database import get_db
from backend.models.candidate import Candidate
from backend.models.job import Job, JobApplication
from backend.models.user import User
from backend.routes import jobs as jobs_routes
from backend.routes.jobs import router


def _client(db) -> TestClient:
    app = FastAPI()
    app.include_router(router)

    def override_get_db() -> Iterator:
        yield db

    app.dependency_overrides[jobs_routes.get_db] = override_get_db
    return TestClient(app)


def _job(db, **overrides):
    candidate = Candidate(name="Riley", folder_path="/tmp/application-pipeline")
    db.add(candidate)
    db.flush()
    fields = {"title": "Backend Engineer", "company": "Acme", "status": "active"}
    fields.update(overrides)
    job = Job(candidate_id=candidate.id, **fields)
    db.add(job)
    db.commit()
    return candidate, job


def test_first_status_change_creates_job_application_row(db):
    _candidate, job = _job(db)
    client = _client(db)

    response = client.post(f"/{job.id}/application-status", data={"status": "applied"}, follow_redirects=False)

    assert response.status_code == 303
    application = db.query(JobApplication).filter_by(job_id=job.id).one()
    assert application.status == "applied"
    assert application.applied_date is not None


def test_status_change_updates_existing_application_row(db):
    _candidate, job = _job(db)
    application = JobApplication(job_id=job.id, status="interested")
    db.add(application)
    db.commit()
    client = _client(db)

    client.post(f"/{job.id}/application-status", data={"status": "interview"}, follow_redirects=False)

    db.refresh(application)
    assert application.status == "interview"
    assert db.query(JobApplication).filter_by(job_id=job.id).count() == 1


def test_invalid_status_is_rejected(db):
    _candidate, job = _job(db)
    client = _client(db)

    response = client.post(f"/{job.id}/application-status", data={"status": "ghosted"})

    assert response.status_code == 400
    assert db.query(JobApplication).filter_by(job_id=job.id).count() == 0


def test_missing_job_returns_404(db):
    client = _client(db)

    response = client.post("/999/application-status", data={"status": "applied"})

    assert response.status_code == 404


def test_application_status_change_is_scoped_to_owning_candidate(db):
    _candidate, job = _job(db)
    other_user = User(email="other@local", display_name="Other User", account_type="job_seeking")
    db.add(other_user)
    db.commit()
    other_candidate = Candidate(name="Jordan", folder_path="/tmp/other-owner", user_id=other_user.id)
    db.add(other_candidate)
    db.commit()
    job.candidate_id = other_candidate.id
    db.commit()
    client = _client(db)

    response = client.post(f"/{job.id}/application-status", data={"status": "applied"})

    assert response.status_code == 404
    assert db.query(JobApplication).filter_by(job_id=job.id).count() == 0


def test_jobs_list_shows_application_status_badge_and_filters(db):
    _candidate, applied_job = _job(db, title="Applied Role")
    db.add(JobApplication(job_id=applied_job.id, status="applied"))
    _candidate2, interested_job = _job(db, title="Untouched Role")
    db.commit()
    client = _client(db)

    all_jobs = client.get("/")
    assert "Applied Role" in all_jobs.text
    assert "Untouched Role" in all_jobs.text

    filtered = client.get("/?application_status=applied")
    assert "Applied Role" in filtered.text
    assert "Untouched Role" not in filtered.text

    interested_only = client.get("/?application_status=interested")
    assert "Untouched Role" in interested_only.text
    assert "Applied Role" not in interested_only.text
