"""R7 saved-search snapshots and sightings-based deduplication."""
import asyncio
import json

from collections.abc import Iterator
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.models.candidate import Candidate
from backend.models.job import Job, SearchRun, SearchRunJob
from backend.services.job_search import JobSearchService, SearchConfig
from backend.database import get_db
from backend.routes import jobs as jobs_routes
from backend.routes.jobs import router


def _client(db) -> TestClient:
    app = FastAPI()
    app.include_router(router)

    def override_get_db() -> Iterator:
        yield db

    app.dependency_overrides[jobs_routes.get_db] = override_get_db
    return TestClient(app)


def _run_search(db, postings, *, run_name):
    service = JobSearchService(db)

    async def fake_linkedin(*_args, **_kwargs):
        return postings

    service._search_linkedin = fake_linkedin
    return asyncio.run(service.search(SearchConfig(
        candidate_id=1, query="Backend Engineer", run_name=run_name,
        platforms=["linkedin"], analyze_with_ai=False,
    )))


def test_known_job_is_attached_to_later_run_not_silently_dropped(db):
    candidate = Candidate(name="Sam", folder_path="/tmp/search-runs")
    db.add(candidate)
    db.commit()

    posting = {
        "title": "Backend Engineer", "company": "Acme", "platform": "linkedin",
        "platform_job_id": "123", "description_hash": "stable-posting", "salary": "$100k",
    }
    first = _run_search(db, [posting], run_name="Initial backend search")
    original = db.query(SearchRunJob).filter_by(search_run_id=first.search_run_id).one()
    original_score = original.deterministic_score
    job = db.query(Job).one()
    job.deterministic_score = 7  # later live recomputation must not rewrite run one
    db.commit()

    second = _run_search(db, [posting], run_name="Follow-up backend search")

    assert db.query(Job).count() == 1
    assert db.query(SearchRun).count() == 2
    memberships = db.query(SearchRunJob).order_by(SearchRunJob.search_run_id).all()
    assert [membership.first_sighting for membership in memberships] == [True, False]
    assert memberships[0].deterministic_score == original_score
    assert memberships[1].deterministic_score == 7
    assert second.jobs_saved == 0
    assert second.total_unique == 1


def test_same_posting_sighted_on_two_platforms_is_one_run_membership(db):
    candidate = Candidate(name="Sam", folder_path="/tmp/search-runs")
    db.add(candidate)
    db.commit()
    service = JobSearchService(db)
    posting = {"title": "Engineer", "company": "Acme", "description_hash": "same"}
    plans = service._plan_run_memberships([
        {**posting, "platform": "linkedin", "platform_job_id": "li-1"},
        {**posting, "platform": "glassdoor", "platform_job_id": "gd-1"},
    ], candidate.id)

    assert len(plans) == 1
    assert plans[0][1] is None
    assert plans[0][2] == ["linkedin", "glassdoor"]


def test_search_run_migration_is_idempotent(db):
    # The fixture's metadata creates these tables; importing the migration here
    # verifies legacy application startup can safely invoke it repeatedly.
    from backend.database import migrate_search_runs

    migrate_search_runs(db.get_bind())
    migrate_search_runs(db.get_bind())


def test_saved_list_routes_render_snapshot_fields(db):
    candidate = Candidate(name="Sam", folder_path="/tmp/search-runs")
    db.add(candidate)
    db.flush()
    job = Job(candidate_id=candidate.id, title="Backend Engineer", company="Acme", status="active")
    db.add(job)
    db.flush()
    search_run = SearchRun(candidate_id=candidate.id, name="July backend", query="Backend Engineer", platforms='["linkedin"]')
    db.add(search_run)
    db.flush()
    db.add(SearchRunJob(
        search_run_id=search_run.id, job_id=job.id, first_sighting=True,
        sighted_platforms='["linkedin"]', deterministic_score=89, salary="$120k",
        verified_remote_status="fully_remote",
    ))
    db.commit()

    response = _client(db).get(f"/lists/{search_run.id}")

    assert response.status_code == 200
    assert "Historical snapshot" in response.text
    # The snapshot status itself remains the stored enum display; controls may
    # independently use title-cased accessibility text.
    assert ">fully remote</td>" in response.text
    assert ">Fully remote</td>" not in response.text
    assert "$120k" in response.text
