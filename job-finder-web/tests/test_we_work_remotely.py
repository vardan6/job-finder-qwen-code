"""Saved-markup contract tests for the WWR adapter; no provider access occurs."""
import pytest
from collections.abc import Iterator
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.database import get_db
from backend.models.candidate import Candidate
from backend.routes import jobs as jobs_routes
from backend.routes.jobs import router
from backend.scrapers.base import JobPlatformAdapter, PlatformJob
from backend.scrapers.we_work_remotely import WeWorkRemotelyScraper
from backend.services.job_search import JobSearchService, SearchConfig


WWR_FIXTURE = """
<ul class="jobs">
  <li class="feature job"><a href="/remote-jobs/1234-senior-test-engineer">
    <span class="company">Acme &amp; Co</span><span class="title">Senior Test Engineer</span>
    <span class="region">Anywhere in the World</span><time class="date">2 days ago</time></a></li>
  <li class="feature job"><a href="/remote-jobs/5678-platform-engineer">
    <span class="company">Beta</span><span class="title">Platform Engineer</span>
    <span class="location">Europe only</span><time class="date">Yesterday</time></a></li>
  <li class="feature job"><a href="/remote-jobs/1234-senior-test-engineer">
    <span class="company">Acme &amp; Co</span><span class="title">Senior Test Engineer</span></a></li>
</ul>
"""


def test_wwr_fixture_normalizes_source_identity_and_remote_eligibility():
    jobs = WeWorkRemotelyScraper.parse_search_page(WWR_FIXTURE)

    assert len(jobs) == 2
    first = jobs[0]
    assert first == PlatformJob(
        title="Senior Test Engineer", company="Acme & Co", location="Anywhere in the World",
        posted_date="2 days ago", job_url="https://weworkremotely.com/remote-jobs/1234-senior-test-engineer",
        platform_job_id="1234", apply_url=None, remote_eligibility="Anywhere in the World",
        source_timestamp="2 days ago",
    )
    assert jobs[1].remote_eligibility == "Europe only"


def test_wwr_parser_respects_limit_and_skips_incomplete_cards():
    html = WWR_FIXTURE + '<li class="feature job"><span class="title">No company</span></li>'
    assert len(WeWorkRemotelyScraper.parse_search_page(html, max_jobs=1)) == 1


@pytest.mark.asyncio
async def test_wwr_live_search_is_explicitly_unimplemented():
    with pytest.raises(NotImplementedError, match="live session navigation"):
        await WeWorkRemotelyScraper().search_jobs("test engineer")


def test_wwr_adapter_has_the_shared_adapter_surface():
    assert isinstance(WeWorkRemotelyScraper(), JobPlatformAdapter)


def test_search_configuration_exposes_wwr_as_policy_gated_and_selectable(db):
    candidate = Candidate(name="Sam", folder_path="/tmp/wwr-config")
    db.add(candidate)
    db.commit()
    app = FastAPI()
    app.include_router(router)

    def override_get_db() -> Iterator:
        yield db

    app.dependency_overrides[jobs_routes.get_db] = override_get_db
    response = TestClient(app).get(f"/api/candidates/{candidate.id}/search-config")

    assert response.status_code == 200
    assert "We Work Remotely" in response.text
    assert 'value="we_work_remotely"' in response.text
    assert "Live access pending authorization" in response.text
    control = response.text.split('id="platform-we_work_remotely"', 1)[1].split(">", 1)[0]
    assert "disabled" not in control


@pytest.mark.asyncio
async def test_wwr_is_registered_but_fails_closed_in_search_service(db):
    candidate = Candidate(name="Sam", folder_path="/tmp/wwr-search")
    db.add(candidate)
    db.commit()

    result = await JobSearchService(db).search(SearchConfig(
        candidate_id=candidate.id,
        query="test engineer",
        platforms=["we_work_remotely"],
        analyze_with_ai=False,
    ))

    assert result.platform_results == {"we_work_remotely": 0}
    assert result.total_found == 0
    assert result.errors == [
        "we_work_remotely search failed: WWR live session navigation is pending the R3 login-health workflow."
    ]
