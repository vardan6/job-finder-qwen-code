"""JobSearchService owns the global search-lock precondition (no route/service split)."""
import asyncio

from backend.models.candidate import Candidate
from backend.services import job_search as job_search_module
from backend.services.job_search import JobSearchService, SearchConfig
from backend.services.search_lock import GlobalSearchLock


def make_candidate(db) -> Candidate:
    candidate = Candidate(name="Sam", folder_path="/tmp/search-lock")
    db.add(candidate)
    db.commit()
    return candidate


def test_search_rejects_when_lock_held(db, tmp_path, monkeypatch):
    lock = GlobalSearchLock(lock_file=str(tmp_path / "search.lock"))
    monkeypatch.setattr(job_search_module, "get_search_lock", lambda: lock)

    candidate = make_candidate(db)
    other_holder = GlobalSearchLock(lock_file=str(tmp_path / "search.lock"))
    assert other_holder.acquire(blocking=False) is True

    result = asyncio.run(JobSearchService(db).search(SearchConfig(
        candidate_id=candidate.id, query="Backend Engineer", platforms=["linkedin"],
    )))

    assert result.success is False
    assert result.search_run_id is None
    assert any("already in progress" in e for e in result.errors)
    other_holder.release()


def test_search_releases_lock_after_completion(db, tmp_path, monkeypatch):
    lock = GlobalSearchLock(lock_file=str(tmp_path / "search.lock"))
    monkeypatch.setattr(job_search_module, "get_search_lock", lambda: lock)

    candidate = make_candidate(db)
    service = JobSearchService(db)

    async def fake_linkedin(*_args, **_kwargs):
        return []

    service._search_linkedin = fake_linkedin

    asyncio.run(service.search(SearchConfig(
        candidate_id=candidate.id, query="Backend Engineer", platforms=["linkedin"],
        analyze_with_ai=False,
    )))

    # A fresh caller must be able to acquire the lock immediately afterward.
    other = GlobalSearchLock(lock_file=str(tmp_path / "search.lock"))
    assert other.acquire(blocking=False) is True
    other.release()


def test_search_releases_lock_on_exception(db, tmp_path, monkeypatch):
    lock = GlobalSearchLock(lock_file=str(tmp_path / "search.lock"))
    monkeypatch.setattr(job_search_module, "get_search_lock", lambda: lock)

    candidate = make_candidate(db)
    service = JobSearchService(db)

    def raise_create_search_run(*_args, **_kwargs):
        raise RuntimeError("db blew up")

    service._create_search_run = raise_create_search_run

    try:
        asyncio.run(service.search(SearchConfig(
            candidate_id=candidate.id, query="Backend Engineer", platforms=["linkedin"],
            analyze_with_ai=False,
        )))
    except RuntimeError:
        pass

    other = GlobalSearchLock(lock_file=str(tmp_path / "search.lock"))
    assert other.acquire(blocking=False) is True
    other.release()
