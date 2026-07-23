"""Exercise data-driven login-wall / CAPTCHA detection through a fake page.

Before block detection was declared as per-platform data evaluated by
``PlaywrightJobScraper``, ``_is_login_wall`` / ``_is_captcha`` were bespoke
methods on each scraper reachable only through a live browser. These tests
drive the real LinkedIn and Glassdoor declarations against a fake page that
only exposes ``url`` and ``query_selector`` — the whole surface the shared
evaluator touches — to lock in the precedence rules.
"""
import asyncio

import pytest

from backend.scrapers import playwright_base
from backend.scrapers.glassdoor import GlassdoorScraper
from backend.scrapers.linkedin import LinkedInScraper


@pytest.fixture(autouse=True)
def _stub_singletons(monkeypatch):
    # Instantiating a scraper otherwise builds the SQLite rate limiter and the
    # deduplicator; block detection uses neither.
    monkeypatch.setattr(playwright_base, "get_rate_limiter", lambda: None)
    monkeypatch.setattr(playwright_base, "get_deduplicator", lambda: None)


class _Page:
    """Minimal page: a URL plus a set of selectors that currently match."""

    def __init__(self, url="https://www.example.com/jobs", present=()):
        self.url = url
        self._present = set(present)

    async def query_selector(self, selector):
        return object() if selector in self._present else None


def _detect(coro):
    return asyncio.run(coro)


# --- LinkedIn ---------------------------------------------------------------

def test_linkedin_login_wall_from_url_token():
    scraper = LinkedInScraper(headless=True)
    page = _Page(url="https://www.linkedin.com/checkpoint/lg/login")
    assert _detect(scraper._is_login_wall(page)) is True


def test_linkedin_login_wall_needs_both_credential_fields():
    scraper = LinkedInScraper(headless=True)
    user_sel, pass_sel = scraper.login_wall_credential_selectors

    # Only the username field present -> not a real sign-in form.
    only_user = _Page(present=[user_sel])
    assert _detect(scraper._is_login_wall(only_user)) is False

    both = _Page(present=[user_sel, pass_sel])
    assert _detect(scraper._is_login_wall(both)) is True


def test_linkedin_clean_results_page_is_not_login_wall():
    scraper = LinkedInScraper(headless=True)
    page = _Page(present=[scraper.results_present_selector])
    assert _detect(scraper._is_login_wall(page)) is False


def test_linkedin_captcha_url_token_blocks_even_with_results():
    scraper = LinkedInScraper(headless=True)
    page = _Page(
        url="https://www.linkedin.com/checkpoint/challenge/verify",
        present=[scraper.results_present_selector],
    )
    assert _detect(scraper._is_captcha(page)) is True


def test_linkedin_rendered_results_win_over_dormant_captcha_widget():
    scraper = LinkedInScraper(headless=True)
    page = _Page(
        present=[scraper.results_present_selector, scraper.captcha_widget_selector],
    )
    assert _detect(scraper._is_captcha(page)) is False


def test_linkedin_visible_captcha_widget_without_results_blocks():
    scraper = LinkedInScraper(headless=True)
    page = _Page(present=[scraper.captcha_widget_selector])
    assert _detect(scraper._is_captcha(page)) is True


def test_linkedin_clean_page_is_not_captcha():
    scraper = LinkedInScraper(headless=True)
    assert _detect(scraper._is_captcha(_Page())) is False


# --- Glassdoor --------------------------------------------------------------

def test_glassdoor_login_wall_from_credential_fields():
    scraper = GlassdoorScraper(headless=True)
    user_sel, pass_sel = scraper.login_wall_credential_selectors
    page = _Page(present=[user_sel, pass_sel])
    assert _detect(scraper._is_login_wall(page)) is True


def test_glassdoor_captcha_url_token_blocks():
    scraper = GlassdoorScraper(headless=True)
    page = _Page(url="https://www.glassdoor.com/px-captcha")
    assert _detect(scraper._is_captcha(page)) is True


def test_glassdoor_listings_present_is_not_captcha():
    scraper = GlassdoorScraper(headless=True)
    page = _Page(
        present=[scraper.results_present_selector, scraper.captcha_widget_selector],
    )
    assert _detect(scraper._is_captcha(page)) is False
