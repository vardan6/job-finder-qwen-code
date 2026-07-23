"""Shared Playwright session lifecycle for browser-based job platform adapters.

LinkedIn and Glassdoor differ only in their search URLs, DOM selectors, result
extraction, and login/CAPTCHA detection. Everything between acquiring the global
search lock and returning normalized ``PlatformJob`` results — rate-limit
gating, browser launch, navigation, block-detection dispatch, the
collect/scroll loop, cookie persistence, and uniform error handling — is
identical across platforms and lives here once.

A concrete adapter keeps its own thin ``search_jobs`` (so platform-specific
parameters stay explicit at the call site) and delegates the session to
``_run_search_session``, overriding only the hooks that describe its platform.
Session outcome is reported through the ``ScraperSessionState`` attributes this
class inherits, so a blocked search still returns a result rather than raising.
"""
import asyncio
import logging
import random
from typing import Callable, List, Optional

from backend.scrapers.base import PlatformJob, ScraperSessionState
from backend.services.browser_manager import get_browser_pool
from backend.services.rate_limiter import get_rate_limiter
from backend.services.search_lock import get_search_lock
from backend.services.job_deduplication import get_deduplicator

logger = logging.getLogger(__name__)


class PlaywrightJobScraper(ScraperSessionState):
    """Template for a stateful, browser-driven job-platform adapter.

    Subclasses declare the per-platform surface via class attributes and the
    hooks below; the shared session skeleton is ``_run_search_session``.
    """

    # --- Per-platform declarations (override in subclass) ---
    platform: str = ""
    label: str = ""  # Human-facing name used verbatim in progress/log messages.
    card_selector: str = ""

    # Navigation. LinkedIn keeps background beacons alive so "networkidle" never
    # fires; such platforms use "domcontentloaded" and rely on the card selector
    # wait inside _collect_jobs instead.
    navigation_wait_until: str = "networkidle"
    navigation_timeout_ms: int = 60000
    pre_navigation_delay: tuple = (2, 4)
    post_navigation_delay: tuple = (1, 2)

    # Result harvesting cadence.
    max_scrolls: int = 5
    scroll_delay: tuple = (2, 3)
    extraction_delay: tuple = (0.5, 1.5)

    # Per-card description panel. When declared, ``_load_job_description``
    # opens the card and reads the detail text; leave empty to skip.
    description_selector: str = ""
    description_click_delay: tuple = (1, 2)

    # Block-detection signatures (evaluated by the shared _is_login_wall /
    # _is_captcha below). Expressed as data so each platform's "what does a
    # login wall / CAPTCHA look like" declaration sits in one readable place
    # and is testable through a fake page.
    login_wall_url_tokens: tuple = ()
    # Both selectors must be present for a login wall (a username-type AND a
    # password-type field), distinguishing a real form from chrome links.
    login_wall_credential_selectors: Optional[tuple] = None
    captcha_url_tokens: tuple = ()
    captcha_widget_selector: str = ""
    # If any of these render, the page is showing real results, so it is not a
    # CAPTCHA regardless of defensive anti-bot scaffolding in the DOM.
    results_present_selector: str = ""

    def __init__(self, headless: bool = False):
        super().__init__()
        self.headless = headless
        self.rate_limiter = get_rate_limiter()
        self.deduplicator = get_deduplicator()
        self.browser_pool = None

    async def __aenter__(self):
        self.browser_pool = get_browser_pool(headless=self.headless)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Keep the browser open when a CAPTCHA was handed to the user to solve.
        if self.browser_pool and not self.manual_challenge_handoff:
            await self.browser_pool.close_all()

    async def _run_search_session(
        self,
        *,
        query: str,
        location: str,
        max_jobs: int,
        cookies_path: Optional[str],
        rate_limit_scope: str,
        rate_limit_settings: Optional[dict] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> List[PlatformJob]:
        """Run one browser search session under the global lock and rate limits.

        Returns a (possibly empty) list of results; blocking conditions
        (rate-limit, login wall, CAPTCHA, errors) are recorded on the inherited
        ``ScraperSessionState`` attributes rather than raised.
        """
        logger.info(
            f"Starting {self.label} search: '{query}' in '{location}' (max: {max_jobs} jobs)"
        )

        def emit(msg: str) -> None:
            if progress_callback:
                progress_callback(msg)

        jobs: List[PlatformJob] = []
        page = None

        try:
            # Acquire global search lock (with timeout to avoid hanging forever)
            lock = get_search_lock()
            if not lock.acquire(blocking=False):
                logger.warning("Another search is in progress, waiting (up to 5 minutes)...")
                if not lock.acquire_with_timeout(timeout_seconds=300):
                    return []

            try:
                # Check rate limits
                allowed, reason = self.rate_limiter.check_rate_limit(
                    rate_limit_scope, rate_limit_settings
                )
                if not allowed:
                    logger.warning(f"{self.label} rate limited: {reason}")
                    self.rate_limited_reason = reason
                    emit(f"{self.label}: Rate limited — {reason}")
                    return []

                # Get browser and page
                emit(f"{self.label}: Launching browser...")
                manager = await self.browser_pool.get_manager()
                page = await manager.new_page(self.platform, cookies_path)

                # Build search URL and navigate with human-like delays
                url = self._build_search_url(query, location)
                logger.info(f"Navigating to: {url}")
                emit(f"{self.label}: Navigating to job search page...")
                await self._human_delay(*self.pre_navigation_delay)
                await page.goto(
                    url,
                    wait_until=self.navigation_wait_until,
                    timeout=self.navigation_timeout_ms,
                )
                await self._human_delay(*self.post_navigation_delay)

                # Check for login wall
                if await self._is_login_wall(page):
                    logger.warning(f"{self.label} login wall detected")
                    emit(f"{self.label}: Login wall detected — session may be expired")
                    self.login_wall_detected = True
                    await manager.save_cookies(self.platform, cookies_path)
                    return []

                # Check for CAPTCHA; platform decides handoff vs. cooldown policy
                if await self._is_captcha(page):
                    await self._on_captcha(
                        page, manager, cookies_path, rate_limit_scope, progress_callback
                    )
                    return []

                emit(f"{self.label}: Page loaded, scanning job listings...")
                jobs = await self._collect_jobs(page, max_jobs, progress_callback=progress_callback)
                logger.info(f"Collected {len(jobs)} jobs from {self.label}")

                # Save cookies
                if cookies_path:
                    await manager.save_cookies(self.platform, cookies_path)

                # Log successful request
                self.rate_limiter.log_request(rate_limit_scope, success=True)
                self.rate_limiter.increment_daily_count(rate_limit_scope)

            finally:
                # Release lock
                lock.release()

        except Exception as e:
            logger.error(f"{self.label} search error: {e}")
            self.last_error = str(e)
            self.rate_limiter.record_failure(rate_limit_scope, str(e))
            emit(f"{self.label}: search failed — {e}")
            # Return empty list instead of re-raising so the orchestrator can continue

        finally:
            if page:
                await page.close()

        return jobs

    async def _collect_jobs(
        self,
        page,
        max_jobs: int,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> List[PlatformJob]:
        """Collect and de-URL-duplicate jobs from a loaded search results page."""
        jobs: List[PlatformJob] = []
        seen_urls = set()

        # Wait for job listings to load
        try:
            await page.wait_for_selector(self.card_selector, timeout=10000)
        except Exception:
            logger.warning("No job listings found on page")
            if progress_callback:
                progress_callback(f"{self.label}: No job listings found on page")
            await self._on_no_cards(page)
            return jobs

        # Scroll through results to load more
        await self._scroll_to_load_more(page)

        # Extract job cards
        job_cards = await page.query_selector_all(self.card_selector)
        logger.info(f"Found {len(job_cards)} job cards")
        if progress_callback:
            progress_callback(f"{self.label}: Found {len(job_cards)} job cards, extracting details...")

        for i, card in enumerate(job_cards):
            if len(jobs) >= max_jobs:
                break

            try:
                job = await self._extract_job_from_card(card, page, i)
                if job and job.job_url not in seen_urls:
                    seen_urls.add(job.job_url)
                    jobs.append(job)
                    logger.debug(f"Extracted job: {job.title} at {job.company}")
                    if progress_callback:
                        progress_callback(
                            f"{self.label} [{len(jobs)}/{min(len(job_cards), max_jobs)}]: "
                            f"{job.title} @ {job.company}"
                        )

                # Random delay between extractions
                await self._human_delay(*self.extraction_delay)

            except Exception as e:
                logger.warning(f"Failed to extract job card {i}: {e}")
                continue

        return jobs

    async def _scroll_to_load_more(self, page):
        """Scroll to load more job results"""
        last_height = await page.evaluate("document.documentElement.scrollHeight")

        for i in range(self.max_scrolls):
            # Scroll down
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await self._human_delay(*self.scroll_delay)

            # Check if more content loaded
            new_height = await page.evaluate("document.documentElement.scrollHeight")

            if new_height == last_height:
                logger.debug(f"No more content after {i + 1} scrolls")
                break

            last_height = new_height

    def _human_delay(self, min_sec: float = 1.0, max_sec: float = 3.0):
        """Random delay to mimic human behavior"""
        delay = random.uniform(min_sec, max_sec)
        return asyncio.sleep(delay)

    # --- Shared DOM readers ---

    async def _text(self, node, selector: str) -> str:
        """Return the trimmed inner text of the first match under ``node``, or ""."""
        el = await node.query_selector(selector)
        return (await el.inner_text()).strip() if el else ""

    async def _has(self, page, selector: str) -> bool:
        """Return True if any element matches ``selector`` (False on error/empty)."""
        if not selector:
            return False
        try:
            return await page.query_selector(selector) is not None
        except Exception:
            return False

    def _url_has_token(self, page, tokens) -> bool:
        url = (getattr(page, "url", "") or "").lower()
        return any(token in url for token in tokens)

    async def _load_job_description(self, card, page):
        """Open one card's detail panel and return (description, snippet, hash).

        The click -> wait -> read -> hash sequence is identical across
        platforms; only ``description_selector`` and the click delay differ.
        Returns (None, None, None) when unavailable so extraction stays simple.
        """
        if not self.description_selector:
            return None, None, None
        try:
            await card.click()
            await self._human_delay(*self.description_click_delay)
            try:
                await page.wait_for_selector(self.description_selector, timeout=5000)
                desc_el = await page.query_selector(self.description_selector)
                if desc_el:
                    description = await desc_el.inner_text()
                    snippet = description[:500] if description else None
                    description_hash = (
                        self.deduplicator.compute_description_hash(description)
                        if description
                        else None
                    )
                    return description, snippet, description_hash
            except Exception:
                logger.warning(f"{self.label}: could not load job description")
        except Exception as e:
            logger.warning(f"{self.label}: failed to open job card: {e}")
        return None, None, None

    # --- Hooks: subclasses override these to describe their platform ---

    def _build_search_url(self, query: str, location: str) -> str:
        """Return the platform search URL for the query/location."""
        raise NotImplementedError

    async def _extract_job_from_card(self, card, page, index: int) -> Optional[PlatformJob]:
        """Extract a single ``PlatformJob`` from one result card, or None."""
        raise NotImplementedError

    async def _is_login_wall(self, page) -> bool:
        """Return True if the page is a login wall rather than results.

        Driven by the platform's declared signatures: a challenge/login URL
        token, or both credential fields of a real sign-in form present.
        """
        try:
            if self._url_has_token(page, self.login_wall_url_tokens):
                return True
            if self.login_wall_credential_selectors:
                user_sel, pass_sel = self.login_wall_credential_selectors
                if await self._has(page, user_sel) and await self._has(page, pass_sel):
                    return True
            return False
        except Exception:
            return False

    async def _is_captcha(self, page) -> bool:
        """Return True if a CAPTCHA/challenge is actually blocking the page.

        A challenge URL token blocks outright; otherwise, rendered results mean
        the page is fine (platforms preload dormant CAPTCHA scaffolding), and
        only a present widget counts. Data-driven so DOM substring false
        positives stay impossible.
        """
        try:
            if self._url_has_token(page, self.captcha_url_tokens):
                return True
            if await self._has(page, self.results_present_selector):
                return False
            return await self._has(page, self.captcha_widget_selector)
        except Exception:
            return False

    async def _on_captcha(
        self,
        page,
        manager,
        cookies_path: Optional[str],
        rate_limit_scope: str,
        progress_callback: Optional[Callable[[str], None]],
    ) -> None:
        """Apply the platform's CAPTCHA policy (cooldown, manual handoff, ...)."""
        return None

    async def _on_no_cards(self, page) -> None:
        """Hook invoked when the card selector never appears (e.g. snapshot)."""
        return None
