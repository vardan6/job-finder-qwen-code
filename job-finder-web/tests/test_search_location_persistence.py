"""Phase 9.5 AFK slice: a corrected search location must persist across page
loads instead of resetting to `candidate.location` every time (the
Armenia/Colombia ambiguity bug). Written to a dedicated
`CandidatePreferences.last_search_location` field, never back onto
`candidate.location` itself, so tuning a search never rewrites profile data.
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.database import get_db
from backend.models.candidate import Candidate
from backend.models.supporting import CandidatePreferences
from backend.routes import jobs as jobs_routes
from backend.routes.jobs import router


def _client(db):
    app = FastAPI()
    app.include_router(router)

    def override_get_db():
        yield db

    app.dependency_overrides[jobs_routes.get_db] = override_get_db
    return TestClient(app)


def _candidate(db, location="Armenia") -> Candidate:
    candidate = Candidate(name="Sam", folder_path="/tmp/search-location", location=location)
    db.add(candidate)
    db.commit()
    return candidate


def test_search_config_defaults_to_candidate_location_when_nothing_saved(db):
    candidate = _candidate(db, location="Armenia")
    client = _client(db)

    response = client.get(f"/api/candidates/{candidate.id}/search-config")

    assert response.status_code == 200
    assert 'value="Armenia"' in response.text


def test_edited_search_location_persists_and_overrides_candidate_location(db, monkeypatch):
    candidate = _candidate(db, location="Armenia")
    client = _client(db)

    async def fake_run_job_search(*args, **kwargs):
        raise AssertionError("search should not actually run in this test")

    monkeypatch.setattr(jobs_routes, "run_job_search", fake_run_job_search)

    response = client.post(
        "/search/start",
        data={
            "candidate_id": candidate.id,
            "query": "Backend Engineer",
            "location": "Yerevan, Armenia",
        },
    )
    assert response.status_code == 200

    db.refresh(candidate)
    assert candidate.location == "Armenia", "profile location must not be overwritten"

    preferences = db.query(CandidatePreferences).filter_by(candidate_id=candidate.id).one()
    assert preferences.last_search_location == "Yerevan, Armenia"

    follow_up = client.get(f"/api/candidates/{candidate.id}/search-config")
    assert follow_up.status_code == 200
    assert 'value="Yerevan, Armenia"' in follow_up.text
