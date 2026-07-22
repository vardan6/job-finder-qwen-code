"""T3 R3 D1-D4: persist expired status on login-wall, gate search on known-bad
status, surface the specific reason in the search-config platform list, and
offer a pre-search "Check LinkedIn connection" probe button."""
import asyncio

from backend.models.candidate import Candidate
from backend.models.platform_account import PlatformAccount
from backend.scrapers.linkedin import LinkedInScraper
from backend.services.job_search import JobSearchService, SearchConfig


def _candidate(db) -> Candidate:
    candidate = Candidate(name="Sam", folder_path="/tmp/login-reliability")
    db.add(candidate)
    db.commit()
    return candidate


def test_login_wall_during_scrape_persists_expired_status(db, monkeypatch):
    candidate = _candidate(db)
    account = PlatformAccount(candidate_id=candidate.id, platform="linkedin", status="active")
    db.add(account)
    db.commit()

    async def fake_search_jobs(self, *args, **kwargs):
        self.login_wall_detected = True
        return []

    monkeypatch.setattr(LinkedInScraper, "search_jobs", fake_search_jobs)

    service = JobSearchService(db)
    jobs = asyncio.run(service._search_linkedin(
        SearchConfig(candidate_id=candidate.id, query="Backend Engineer"), candidate,
    ))

    assert jobs == []
    db.refresh(account)
    assert account.status == "expired"


def test_search_skips_scrape_when_session_already_known_expired(db, monkeypatch):
    candidate = _candidate(db)
    account = PlatformAccount(candidate_id=candidate.id, platform="linkedin", status="expired")
    db.add(account)
    db.commit()

    called = False

    async def fake_search_jobs(self, *args, **kwargs):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(LinkedInScraper, "search_jobs", fake_search_jobs)

    service = JobSearchService(db)
    jobs = asyncio.run(service._search_linkedin(
        SearchConfig(candidate_id=candidate.id, query="Backend Engineer"), candidate,
    ))

    assert jobs == []
    assert called is False


def test_search_skips_scrape_when_captcha_required(db, monkeypatch):
    candidate = _candidate(db)
    account = PlatformAccount(candidate_id=candidate.id, platform="linkedin", status="captcha_required")
    db.add(account)
    db.commit()

    called = False

    async def fake_search_jobs(self, *args, **kwargs):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(LinkedInScraper, "search_jobs", fake_search_jobs)

    service = JobSearchService(db)
    jobs = asyncio.run(service._search_linkedin(
        SearchConfig(candidate_id=candidate.id, query="Backend Engineer"), candidate,
    ))

    assert jobs == []
    assert called is False


def test_search_config_platform_status_surfaces_expired_reason(db):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.database import get_db
    from backend.routes import jobs as jobs_routes
    from backend.routes.jobs import router

    candidate = _candidate(db)
    account = PlatformAccount(candidate_id=candidate.id, platform="linkedin", status="expired")
    db.add(account)
    db.commit()

    app = FastAPI()
    app.include_router(router)

    def override_get_db():
        yield db

    app.dependency_overrides[jobs_routes.get_db] = override_get_db
    client = TestClient(app)

    response = client.get(f"/api/candidates/{candidate.id}/search-config")

    assert response.status_code == 200
    assert "Session expired" in response.text


def test_search_config_offers_probe_button_for_known_account(db):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.database import get_db
    from backend.routes import jobs as jobs_routes
    from backend.routes.jobs import router

    candidate = _candidate(db)
    account = PlatformAccount(candidate_id=candidate.id, platform="linkedin", status="expired")
    db.add(account)
    db.commit()

    app = FastAPI()
    app.include_router(router)

    def override_get_db():
        yield db

    app.dependency_overrides[jobs_routes.get_db] = override_get_db
    client = TestClient(app)

    response = client.get(f"/api/candidates/{candidate.id}/search-config")

    assert response.status_code == 200
    assert "Check LinkedIn connection" in response.text
    assert f"checkLinkedInConnection({account.id}," in response.text


def test_search_config_omits_probe_button_when_no_account_exists(db):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.database import get_db
    from backend.routes import jobs as jobs_routes
    from backend.routes.jobs import router

    candidate = _candidate(db)

    app = FastAPI()
    app.include_router(router)

    def override_get_db():
        yield db

    app.dependency_overrides[jobs_routes.get_db] = override_get_db
    client = TestClient(app)

    response = client.get(f"/api/candidates/{candidate.id}/search-config")

    assert response.status_code == 200
    assert "Check LinkedIn connection" not in response.text
