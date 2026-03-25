"""
Glassdoor Job Scraper

Ultra-conservative scraping with anti-detection:
- Respects rate limits (10-20s delay, 10/hour, 50/day)
- Operating hours only (8 AM - 10 PM)
- Human-like behavior (random delays, mouse movements)
- Stealth browser configuration
- Automatic cooldown on CAPTCHA/blocks
"""
import asyncio
import logging
import random
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from playwright.async_api import Page

from backend.services.browser_manager import get_browser_pool
from backend.services.rate_limiter import get_rate_limiter
from backend.services.search_lock import get_search_lock
from backend.services.job_deduplication import get_deduplicator

logger = logging.getLogger(__name__)


@dataclass
class GlassdoorJob:
    """Represents a job found on Glassdoor"""
    
    title: str
    company: str
    location: str
    posted_date: Optional[str]
    job_url: str
    platform_job_id: Optional[str]
    description: Optional[str] = None
    description_hash: Optional[str] = None
    snippet: Optional[str] = None
    salary: Optional[str] = None
    job_type: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "posted_date": self.posted_date,
            "job_url": self.job_url,
            "platform_job_id": self.platform_job_id,
            "description": self.description,
            "description_hash": self.description_hash,
            "snippet": self.snippet,
            "salary": self.salary,
            "job_type": self.job_type,
        }


# Glassdoor search URL template
GLASSDOOR_SEARCH_URL = "https://www.glassdoor.com/Job/jobs.htm"


class GlassdoorScraper:
    """Scraper for Glassdoor Jobs"""
    
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.rate_limiter = get_rate_limiter()
        self.deduplicator = get_deduplicator()
        self.browser_pool = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.browser_pool = get_browser_pool(headless=self.headless)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.browser_pool:
            await self.browser_pool.close_all()
    
    async def search_jobs(
        self,
        query: str,
        location: str = "",
        max_jobs: int = 20,
        cookies_path: Optional[str] = None,
    ) -> List[GlassdoorJob]:
        """
        Search for jobs on Glassdoor.
        
        Args:
            query: Job search query (e.g., "Python Engineer")
            location: Location filter (e.g., "United States", "Remote")
            max_jobs: Maximum number of jobs to collect
            cookies_path: Path to load/save session cookies
        
        Returns:
            List of GlassdoorJob objects
        """
        logger.info(f"Starting Glassdoor search: '{query}' in '{location}' (max: {max_jobs} jobs)")
        
        jobs = []
        page = None
        
        try:
            # Acquire global search lock
            lock = get_search_lock()
            if not lock.acquire(blocking=False):
                logger.warning("Another search is in progress, waiting...")
                if not lock.acquire(blocking=True):
                    return []
            
            try:
                # Check rate limits
                allowed, reason = self.rate_limiter.check_rate_limit("glassdoor")
                if not allowed:
                    logger.warning(f"Glassdoor rate limited: {reason}")
                    return []
                
                # Get browser and page
                manager = await self.browser_pool.get_manager()
                page = await manager.new_page("glassdoor", cookies_path)
                
                # Build search URL
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
                
                logger.info(f"Navigating to: {url}")
                
                # Navigate with human-like delay
                await self._human_delay(3, 5)  # Glassdoor is more sensitive
                await page.goto(url, wait_until="networkidle", timeout=60000)
                await self._human_delay(2, 3)
                
                # Check for login wall
                if await self._is_login_wall(page):
                    logger.warning("Glassdoor login wall detected")
                    await manager.save_cookies("glassdoor", cookies_path)
                    return []
                
                # Check for CAPTCHA
                if await self._is_captcha(page):
                    logger.error("Glassdoor CAPTCHA detected, setting cooldown")
                    self.rate_limiter.record_failure("glassdoor", "CAPTCHA detected")
                    await manager.save_cookies("glassdoor", cookies_path)
                    return []
                
                # Collect jobs from search results
                jobs = await self._collect_jobs(page, max_jobs)
                logger.info(f"Collected {len(jobs)} jobs from Glassdoor")
                
                # Save cookies
                if cookies_path:
                    await manager.save_cookies("glassdoor", cookies_path)
                
                # Log successful request
                self.rate_limiter.log_request("glassdoor", success=True)
                self.rate_limiter.increment_daily_count("glassdoor")
                
            finally:
                # Release lock
                lock.release()
        
        except Exception as e:
            logger.error(f"Glassdoor search error: {e}")
            self.rate_limiter.record_failure("glassdoor", str(e))
            raise
        
        finally:
            if page:
                await page.close()
        
        return jobs
    
    async def _collect_jobs(self, page: Page, max_jobs: int) -> List[GlassdoorJob]:
        """Collect jobs from search results page"""
        jobs = []
        seen_urls = set()
        
        # Wait for job listings to load
        try:
            await page.wait_for_selector('[data-test="jobListing"]', timeout=10000)
        except Exception:
            logger.warning("No job listings found on page")
            return jobs
        
        # Scroll through results to load more
        await self._scroll_to_load_more(page)
        
        # Extract job cards
        job_cards = await page.query_selector_all('[data-test="jobListing"]')
        logger.info(f"Found {len(job_cards)} job cards")
        
        for i, card in enumerate(job_cards):
            if len(jobs) >= max_jobs:
                break
            
            try:
                # Extract job data
                job = await self._extract_job_from_card(card, page, i)
                if job and job.job_url not in seen_urls:
                    seen_urls.add(job.job_url)
                    jobs.append(job)
                    logger.debug(f"Extracted job: {job.title} at {job.company}")
                
                # Random delay between extractions
                await self._human_delay(1, 2)
                
            except Exception as e:
                logger.warning(f"Failed to extract job card {i}: {e}")
                continue
        
        return jobs
    
    async def _extract_job_from_card(self, card, page: Page, index: int) -> Optional[GlassdoorJob]:
        """Extract job information from a job card"""
        try:
            # Extract title
            title_el = await card.query_selector('[data-test="job-title"]')
            title = (await title_el.inner_text()).strip() if title_el else ""
            
            # Extract company
            company_el = await card.query_selector('[data-test="employer-name"]')
            company = (await company_el.inner_text()).strip() if company_el else ""
            
            # Extract location
            location_el = await card.query_selector('[data-test="job-location"]')
            location = (await location_el.inner_text()).strip() if location_el else ""
            
            # Extract posted date
            posted_el = await card.query_selector('[data-test="job-age"]')
            posted_date = (await posted_el.inner_text()).strip() if posted_el else ""
            
            # Extract salary if available
            salary = None
            salary_el = await card.query_selector('[data-test="job-salary"]')
            if salary_el:
                salary = (await salary_el.inner_text()).strip()
            
            # Extract job type if available
            job_type = None
            job_type_el = await card.query_selector('[data-test="job-type"]')
            if job_type_el:
                job_type = (await job_type_el.inner_text()).strip()
            
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
            
            # Get description by clicking on job
            description = None
            description_hash = None
            snippet = None
            
            try:
                # Click to open job details
                await card.click()
                await self._human_delay(2, 3)
                
                # Wait for description panel
                try:
                    await page.wait_for_selector('[data-test="job-description"]', timeout=5000)
                    desc_el = await page.query_selector('[data-test="job-description"]')
                    if desc_el:
                        description = await desc_el.inner_text()
                        snippet = description[:500] if description else None
                        
                        # Compute hash
                        if description:
                            description_hash = self.deduplicator.compute_description_hash(description)
                
                except Exception:
                    logger.warning(f"Could not load description for job {index}")
                
            except Exception as e:
                logger.warning(f"Failed to click job card: {e}")
            
            return GlassdoorJob(
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
    
    async def _scroll_to_load_more(self, page: Page, max_scrolls: int = 3):
        """Scroll to load more job results"""
        last_height = await page.evaluate("document.documentElement.scrollHeight")
        
        for i in range(max_scrolls):
            # Scroll down
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await self._human_delay(3, 4)  # Glassdoor loads slower
            
            # Check if more content loaded
            new_height = await page.evaluate("document.documentElement.scrollHeight")
            
            if new_height == last_height:
                logger.debug(f"No more content after {i + 1} scrolls")
                break
            
            last_height = new_height
    
    async def _is_login_wall(self, page: Page) -> bool:
        """Check if login wall is present"""
        try:
            url = (page.url or "").lower()
            if any(token in url for token in ["/profile/login", "login_input", "signin", "member/home/login"]):
                return True

            # Real login form indicators
            has_email = await page.query_selector('input[type="email"], input[name*="email"]') is not None
            has_password = await page.query_selector('input[type="password"]') is not None
            if has_email and has_password:
                return True

            # If job listings exist, we're past login wall.
            has_listings = await page.query_selector('[data-test="jobListing"], .JobsList_jobListItem__wjTHv') is not None
            if has_listings:
                return False

            return False
        except Exception:
            return False
    
    async def _is_captcha(self, page: Page) -> bool:
        """Check if CAPTCHA is present"""
        captcha_indicators = [
            "captcha",
            "verify you are human",
            "unusual traffic",
            "access denied",
        ]
        
        try:
            content = await page.content()
            content_lower = content.lower()
            return any(indicator in content_lower for indicator in captcha_indicators)
        except Exception:
            return False
    
    def _human_delay(self, min_sec: float = 1.0, max_sec: float = 3.0):
        """Random delay to mimic human behavior"""
        delay = random.uniform(min_sec, max_sec)
        return asyncio.sleep(delay)


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
