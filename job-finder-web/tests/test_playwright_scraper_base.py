"""Directly exercise the shared Playwright session lifecycle.

Before ``PlaywrightJobScraper`` existed this orchestration was duplicated
verbatim in the LinkedIn and Glassdoor scrapers and only reachable through a
live browser, so it was effectively untested. These tests drive the template
with fake page/manager/browser-pool objects to lock in each session outcome:
happy path, rate-limit gate, login wall, CAPTCHA policy, and error handling.
"""
import asyncio

import pytest

from backend.scrapers import playwright_base
from backend.scrapers.base import PlatformJob
from backend.scrapers.playwright_base import PlaywrightJobScraper


class _FakeLock:
    def acquire(self, blocking=False):
        return True

    def acquire_with_timeout(self, timeout_seconds):
        return True

    def release(self):
        pass


@pytest.fixture(autouse=True)
def _stub_lock(monkeypatch):
    monkeypatch.setattr(playwright_base, "get_search_lock", lambda: _FakeLock())


class _FakePage:
    def __init__(self, *, url="https://stub/jobs", cards=0, goto_error=None):
        self.url = url
        self._cards = cards
        self._goto_error = goto_error
        self.closed = False

    async def goto(self, url, wait_until=None, timeout=None):
        if self._goto_error:
            raise self._goto_error

    async def wait_for_selector(self, selector, timeout=None):
        if self._cards == 0:
            raise RuntimeError("no cards")
        return True

    async def query_selector_all(self, selector):
        return list(range(self._cards))

    async def query_selector(self, selector):
        return None

    async def evaluate(self, script):
        return 100  # constant height -> scrolling stops after one pass

    async def content(self):
        return "<html></html>"

    async def close(self):
        self.closed = True


class _FakeManager:
    def __init__(self, page):
        self._page = page
        self.new_page_calls = 0
        self.saved = []
        self.handoffs = []

    async def new_page(self, platform, cookies_path):
        self.new_page_calls += 1
        return self._page

    async def save_cookies(self, platform, cookies_path):
        self.saved.append((platform, cookies_path))

    async def handoff_page_to_manual_login(self, page, key, path):
        self.handoffs.append((key, path))


class _FakePool:
    def __init__(self, manager):
        self._manager = manager
        self.closed = False

    async def get_manager(self):
        return self._manager

    async def close_all(self):
        self.closed = True


class _FakeRateLimiter:
    def __init__(self, allowed=True, reason=None):
        self._allowed = allowed
        self._reason = reason
        self.failures = []
        self.logged = []
        self.incremented = []

    def check_rate_limit(self, scope, settings=None):
        return (self._allowed, self._reason)

    def log_request(self, scope, success=True):
        self.logged.append((scope, success))

    def increment_daily_count(self, scope):
        self.incremented.append(scope)

    def record_failure(self, scope, reason):
        self.failures.append((scope, reason))


class _StubScraper(PlaywrightJobScraper):
    platform = "stub"
    label = "Stub"
    card_selector = ".card"
    pre_navigation_delay = (0, 0)
    post_navigation_delay = (0, 0)
    scroll_delay = (0, 0)
    extraction_delay = (0, 0)
    max_scrolls = 1

    def __init__(self, *, login_wall=False, captcha=False):
        super().__init__(headless=True)
        self._login_wall = login_wall
        self._captcha = captcha
        self.captcha_handled = False

    def _build_search_url(self, query, location):
        return f"https://stub/search?q={query}"

    async def _is_login_wall(self, page):
        return self._login_wall

    async def _is_captcha(self, page):
        return self._captcha

    async def _on_captcha(self, page, manager, cookies_path, rate_limit_scope, progress_callback):
        self.captcha_handled = True
        self.rate_limited_reason = "CAPTCHA detected"

    async def _extract_job_from_card(self, card, page, index):
        return PlatformJob(
            title=f"Job {index}", company="Acme", location="Remote",
            posted_date=None, job_url=f"https://stub/jobs/{index}",
            platform_job_id=str(index),
        )


def _run(scraper, page, *, rate_limiter=None, cookies_path="/tmp/stub.enc"):
    manager = _FakeManager(page)
    scraper.browser_pool = _FakePool(manager)
    scraper.rate_limiter = rate_limiter or _FakeRateLimiter()
    jobs = asyncio.run(scraper._run_search_session(
        query="engineer", location="Remote", max_jobs=10,
        cookies_path=cookies_path, rate_limit_scope="stub",
    ))
    return jobs, manager, scraper.rate_limiter


def test_happy_path_collects_saves_and_logs_success():
    page = _FakePage(cards=3)
    scraper = _StubScraper()

    jobs, manager, limiter = _run(scraper, page)

    assert [j.title for j in jobs] == ["Job 0", "Job 1", "Job 2"]
    assert manager.saved == [("stub", "/tmp/stub.enc")]
    assert limiter.logged == [("stub", True)]
    assert limiter.incremented == ["stub"]
    assert scraper.last_error is None
    assert scraper.rate_limited_reason is None
    assert page.closed is True


def test_rate_limited_never_launches_browser():
    page = _FakePage(cards=3)
    scraper = _StubScraper()

    jobs, manager, limiter = _run(
        scraper, page, rate_limiter=_FakeRateLimiter(allowed=False, reason="hourly cap"),
    )

    assert jobs == []
    assert scraper.rate_limited_reason == "hourly cap"
    assert manager.new_page_calls == 0
    assert limiter.logged == []


def test_login_wall_flags_state_and_skips_success_logging():
    page = _FakePage(cards=3)
    scraper = _StubScraper(login_wall=True)

    jobs, manager, limiter = _run(scraper, page)

    assert jobs == []
    assert scraper.login_wall_detected is True
    assert manager.saved == [("stub", "/tmp/stub.enc")]
    assert limiter.logged == []


def test_captcha_delegates_to_policy_hook():
    page = _FakePage(cards=3)
    scraper = _StubScraper(captcha=True)

    jobs, _manager, limiter = _run(scraper, page)

    assert jobs == []
    assert scraper.captcha_handled is True
    assert scraper.rate_limited_reason == "CAPTCHA detected"
    assert limiter.logged == []


def test_navigation_error_is_recorded_not_raised():
    page = _FakePage(cards=3, goto_error=RuntimeError("boom"))
    scraper = _StubScraper()

    jobs, _manager, limiter = _run(scraper, page)

    assert jobs == []
    assert scraper.last_error == "boom"
    assert limiter.failures == [("stub", "boom")]
    assert page.closed is True


def test_no_cards_returns_empty_without_error():
    page = _FakePage(cards=0)
    scraper = _StubScraper()

    jobs, _manager, limiter = _run(scraper, page)

    assert jobs == []
    assert scraper.last_error is None
    # A no-results page is still a successful, rate-limited request.
    assert limiter.logged == [("stub", True)]
