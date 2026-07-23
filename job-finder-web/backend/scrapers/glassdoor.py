"""
Glassdoor Job Scraper

Ultra-conservative scraping with anti-detection:
- Respects rate limits (10-20s delay, 10/hour, 50/day)
- Operating hours only (8 AM - 10 PM)
- Human-like behavior (random delays, mouse movements)
- Stealth browser configuration
- Automatic cooldown on CAPTCHA/blocks

Only the Glassdoor-specific surface lives here; the shared browser session
lifecycle is owned by ``PlaywrightJobScraper``.
"""
import logging
import re
from typing import Callable, List, Optional

from playwright.async_api import Page

from backend.scrapers.base import PlatformJob
from backend.scrapers.playwright_base import PlaywrightJobScraper

logger = logging.getLogger(__name__)


# Glassdoor search URL template
GLASSDOOR_SEARCH_URL = "https://www.glassdoor.com/Job/jobs.htm"


class GlassdoorScraper(PlaywrightJobScraper):
    """Scraper for Glassdoor Jobs"""

    platform = "glassdoor"
    label = "Glassdoor"
    card_selector = '[data-test="jobListing"]'

    # Glassdoor is more sensitive; navigate slowly and scroll conservatively.
    navigation_wait_until = "networkidle"
    navigation_timeout_ms = 60000
    pre_navigation_delay = (3, 5)
    post_navigation_delay = (2, 3)
    max_scrolls = 3
    scroll_delay = (3, 4)
    extraction_delay = (1, 2)

    description_selector = '[data-test="job-description"]'
    description_click_delay = (2, 3)

    # Block-detection signatures (evaluated by PlaywrightJobScraper).
    login_wall_url_tokens = (
        "/profile/login",
        "login_input",
        "signin",
        "member/home/login",
    )
    login_wall_credential_selectors = (
        'input[type="email"], input[name*="email"]',
        'input[type="password"]',
    )
    captcha_url_tokens = ("/verify", "unusual traffic", "px-captcha", "access denied")
    results_present_selector = '[data-test="jobListing"]'
    captcha_widget_selector = (
        "iframe[src*='captcha' i], iframe[title*='captcha' i], "
        ".g-recaptcha, .h-captcha, #px-captcha, [id*='captcha' i]"
    )

    async def search_jobs(
        self,
        query: str,
        location: str = "",
        max_jobs: int = 20,
        cookies_path: Optional[str] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> List[PlatformJob]:
        """Search for jobs on Glassdoor."""
        return await self._run_search_session(
            query=query,
            location=location,
            max_jobs=max_jobs,
            cookies_path=cookies_path,
            rate_limit_scope="glassdoor",
            progress_callback=progress_callback,
        )

    def _build_search_url(self, query: str, location: str) -> str:
        params = {
            "sc.keyword": query,
            "locT": "C",
            "locId": "1",  # United States
            "jobType": "all",
            "sortBy": "relevance",
        }
        if location:
            params["location"] = location

        url = GLASSDOOR_SEARCH_URL
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
        logger.error("Glassdoor CAPTCHA detected, setting cooldown")
        if progress_callback:
            progress_callback("Glassdoor: CAPTCHA detected — setting cooldown")
        self.rate_limited_reason = "CAPTCHA detected"
        self.rate_limiter.record_failure(rate_limit_scope, "CAPTCHA detected")
        await manager.save_cookies(self.platform, cookies_path)

    async def _extract_job_from_card(self, card, page: Page, index: int) -> Optional[PlatformJob]:
        """Extract job information from a job card"""
        try:
            title = await self._text(card, '[data-test="job-title"]')
            company = await self._text(card, '[data-test="employer-name"]')
            location = await self._text(card, '[data-test="job-location"]')
            posted_date = await self._text(card, '[data-test="job-age"]')
            salary = await self._text(card, '[data-test="job-salary"]') or None
            job_type = await self._text(card, '[data-test="job-type"]') or None

            # Extract job URL
            link_el = await card.query_selector("a.jobLink")
            if not link_el:
                link_el = await card.query_selector("a")

            if not link_el:
                return None

            href = await link_el.get_attribute("href")
            job_url = href.split("?")[0] if href else ""

            # Extract platform job ID from URL
            platform_job_id = None
            if job_url:
                match = re.search(r"JobListing-(\d+)", job_url)
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
                salary=salary,
                job_type=job_type,
            )

        except Exception as e:
            logger.warning(f"Error extracting job card: {e}")
            return None


async def scrape_glassdoor_jobs(
    query: str,
    location: str = "",
    max_jobs: int = 20,
    cookies_path: Optional[str] = None,
    headless: bool = False,
) -> List[dict]:
    """
    Convenience function to scrape Glassdoor jobs.

    Args:
        query: Search query
        location: Location filter
        max_jobs: Maximum jobs to collect
        cookies_path: Path to cookies file
        headless: Run browser in headless mode

    Returns:
        List of job dictionaries
    """
    async with GlassdoorScraper(headless=headless) as scraper:
        jobs = await scraper.search_jobs(query, location, max_jobs, cookies_path)
        return [job.to_dict() for job in jobs]
