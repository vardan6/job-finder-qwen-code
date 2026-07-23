"""
LinkedIn Job Scraper

Ultra-conservative scraping with anti-detection:
- Respects rate limits (8-15s delay, 20/hour, 100/day)
- Operating hours only (8 AM - 10 PM)
- Human-like behavior (random delays, mouse movements)
- Stealth browser configuration
- Automatic cooldown on CAPTCHA/blocks

Only the LinkedIn-specific surface lives here; the shared browser session
lifecycle is owned by ``PlaywrightJobScraper``.
"""
import logging
import re
from datetime import datetime
from typing import Callable, List, Optional

from playwright.async_api import Page

from backend.config import DATA_DIR
from backend.scrapers.base import PlatformJob
from backend.scrapers.playwright_base import PlaywrightJobScraper

logger = logging.getLogger(__name__)


# LinkedIn search URL templates
LINKEDIN_SEARCH_URL = "https://www.linkedin.com/jobs/search"

# Job card selector for the authenticated jobs-search DOM (LinkedIn's own
# structural classes; the visual/utility classes on these elements are
# randomized per-build and unusable as selectors).
JOB_CARD_SELECTOR = "div.job-card-container[data-job-id]"
POSTED_DATE_RE = re.compile(
    r"\d+\s+(?:minute|hour|day|week|month)s?\s+ago", re.IGNORECASE
)


class LinkedInScraper(PlaywrightJobScraper):
    """Scraper for LinkedIn Jobs"""

    platform = "linkedin"
    label = "LinkedIn"
    card_selector = JOB_CARD_SELECTOR

    # LinkedIn keeps background requests (analytics/beacons) running
    # indefinitely, so "networkidle" routinely never fires and goto would
    # otherwise hang for the full timeout on every search. "domcontentloaded"
    # is enough here since _collect_jobs separately waits for the job-card
    # selector to appear.
    navigation_wait_until = "domcontentloaded"
    navigation_timeout_ms = 30000
    pre_navigation_delay = (2, 4)
    post_navigation_delay = (1, 2)
    max_scrolls = 5
    scroll_delay = (2, 3)
    extraction_delay = (0.5, 1.5)

    description_selector = ".jobs-box__html-content"

    # Block-detection signatures (evaluated by PlaywrightJobScraper).
    login_wall_url_tokens = ("/login", "/checkpoint", "/authwall", "challenge")
    login_wall_credential_selectors = (
        'input[name="session_key"], input#username',
        'input[name="session_password"], input#password',
    )
    captcha_url_tokens = (
        "/checkpoint/challenge",
        "/checkpoint/challengesv2",
        "unusual traffic",
    )
    results_present_selector = ".job-search-card, .jobs-search__results-list li"
    # LinkedIn preloads dormant CAPTCHA scaffolding, so require a *visible*
    # widget rather than mere DOM presence.
    captcha_widget_selector = (
        "iframe[src*='captcha' i]:visible, iframe[title*='captcha' i]:visible, "
        ".g-recaptcha:visible, .h-captcha:visible, #captcha-internal:visible, "
        "[id*='captcha' i]:visible"
    )

    # Manual-login handoff targets, populated per search by search_jobs.
    _manual_session_key: Optional[str] = None
    _manual_profile_path: Optional[str] = None

    async def search_jobs(
        self,
        query: str,
        location: str = "",
        max_jobs: int = 20,
        cookies_path: Optional[str] = None,
        rate_limit_scope: str = "linkedin",
        rate_limit_settings: Optional[dict] = None,
        manual_session_key: Optional[str] = None,
        manual_profile_path: Optional[str] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> List[PlatformJob]:
        """Search for jobs on LinkedIn."""
        self._manual_session_key = manual_session_key
        self._manual_profile_path = manual_profile_path
        return await self._run_search_session(
            query=query,
            location=location,
            max_jobs=max_jobs,
            cookies_path=cookies_path,
            rate_limit_scope=rate_limit_scope,
            rate_limit_settings=rate_limit_settings,
            progress_callback=progress_callback,
        )

    def _build_search_url(self, query: str, location: str) -> str:
        params = {
            "keywords": query,
            "location": location,
            "f_AL": "true",  # Remote filter
            "sortBy": "R",  # Relevance
        }
        url = LINKEDIN_SEARCH_URL
        url_params = "&".join(f"{k}={v}" for k, v in params.items() if v)
        if url_params:
            url += f"?{url_params}"
        return url

    async def _on_captcha(
        self,
        page: Page,
        manager,
        cookies_path: Optional[str],
        rate_limit_scope: str,
        progress_callback: Optional[Callable[[str], None]],
    ) -> None:
        logger.error("LinkedIn CAPTCHA detected; handing browser to the user")
        if progress_callback:
            progress_callback(
                "LinkedIn: CAPTCHA detected — solve it in the open browser, then click Finish Browser Login"
            )
        self.rate_limiter.record_failure(rate_limit_scope, "CAPTCHA detected")
        await manager.save_cookies(self.platform, cookies_path)
        if self._manual_session_key and self._manual_profile_path:
            await manager.handoff_page_to_manual_login(
                page, self._manual_session_key, self._manual_profile_path,
            )
            self.manual_challenge_handoff = True

    async def _on_no_cards(self, page: Page) -> None:
        await self._dump_debug_snapshot(page, "no_job_cards")

    async def _extract_job_from_card(self, card, page: Page, index: int) -> Optional[PlatformJob]:
        """Extract job information from a job card"""
        try:
            # Extract title + job URL from the card's title link. The link text
            # is wrapped in nested spans, but its aria-label holds the plain title.
            link_el = await card.query_selector(
                "a.job-card-list__title--link, a.job-card-container__link"
            )
            if not link_el:
                return None

            title = ((await link_el.get_attribute("aria-label")) or "").strip()
            if not title:
                title = (await link_el.inner_text()).strip()

            href = await link_el.get_attribute("href")
            job_url = href.split("?")[0] if href else ""
            # LinkedIn's job-card links are host-relative ("/jobs/view/...");
            # store an absolute URL so it's directly usable outside the app.
            if job_url.startswith("/"):
                job_url = f"https://www.linkedin.com{job_url}"

            # Extract company
            company = await self._text(card, ".artdeco-entity-lockup__subtitle")

            # Extract location (first metadata line under the title)
            location = await self._text(
                card, ".job-card-container__metadata-wrapper li"
            )

            # Posted date isn't a dedicated element in the current DOM; it only
            # appears as free text (e.g. "3 days ago") mixed in with other
            # footer badges like "Viewed"/"Easy Apply", so scan the card text.
            card_text = await card.inner_text()
            posted_match = POSTED_DATE_RE.search(card_text)
            posted_date = posted_match.group(0) if posted_match else ""

            # Extract platform job ID from URL
            platform_job_id = None
            if job_url:
                match = re.search(r"/jobs/view/(\d+)", job_url)
                if match:
                    platform_job_id = match.group(1)

            # Open the job to read its full description.
            description, snippet, description_hash = await self._load_job_description(
                card, page
            )

            return PlatformJob(
                title=title,
                company=company,
                location=location,
                posted_date=posted_date,
                job_url=job_url,
                platform_job_id=platform_job_id,
                description=description,
                description_hash=description_hash,
                snippet=snippet,
            )

        except Exception as e:
            logger.warning(f"Error extracting job card: {e}")
            return None

    async def _dump_debug_snapshot(self, page: Page, label: str):
        """Save the live page HTML when scraping hits an unexpected state.

        LinkedIn's authenticated job-search DOM has drifted from the
        `.job-search-card` selectors this scraper targets before, so blind
        selector guesses risk silently extracting nothing (or the wrong
        thing) again. A real snapshot gives the next fix concrete markup
        instead of another guess.
        """
        try:
            debug_dir = DATA_DIR / "debug"
            debug_dir.mkdir(parents=True, exist_ok=True)
            path = debug_dir / f"linkedin_{label}_{datetime.now():%Y%m%d_%H%M%S}.html"
            path.write_text(await page.content(), encoding="utf-8")
            logger.info(f"Saved LinkedIn debug snapshot to {path}")
        except Exception as e:
            logger.warning(f"Could not save LinkedIn debug snapshot: {e}")


async def scrape_linkedin_jobs(
    query: str,
    location: str = "",
    max_jobs: int = 20,
    cookies_path: Optional[str] = None,
    headless: bool = False,
) -> List[dict]:
    """
    Convenience function to scrape LinkedIn jobs.

    Args:
        query: Search query
        location: Location filter
        max_jobs: Maximum jobs to collect
        cookies_path: Path to cookies file
        headless: Run browser in headless mode

    Returns:
        List of job dictionaries
    """
    async with LinkedInScraper(headless=headless) as scraper:
        jobs = await scraper.search_jobs(query, location, max_jobs, cookies_path)
        return [job.to_dict() for job in jobs]
