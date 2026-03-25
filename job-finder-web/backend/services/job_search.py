"""
Job Search Service - Main orchestrator for job searching

Coordinates:
- Multiple platform scrapers (LinkedIn, Glassdoor)
- Rate limiting and search locks
- AI job analysis
- Deduplication
- Database storage
"""
import asyncio
import logging
import os
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from backend.models.candidate import Candidate
from backend.models.job import Job
from backend.models.platform_account import PlatformAccount
from backend.security import decrypt_json, encrypt_data
from backend.services.job_analysis import get_job_analysis_service, JobAnalysis
from backend.services.job_deduplication import get_deduplicator, check_duplicate_in_db
from backend.services.rate_limiter import get_rate_limiter
from backend.scrapers.linkedin import LinkedInScraper, LinkedInJob
from backend.scrapers.glassdoor import GlassdoorScraper, GlassdoorJob

logger = logging.getLogger(__name__)


@dataclass
class SearchConfig:
    """Configuration for a job search"""
    
    candidate_id: int
    query: str
    location: str = ""
    platforms: List[str] = None
    max_jobs_per_platform: int = 20
    analyze_with_ai: bool = True
    headless: bool = False
    
    def __post_init__(self):
        if self.platforms is None:
            self.platforms = ["linkedin", "glassdoor"]
        elif isinstance(self.platforms, str):
            self.platforms = [self.platforms]
        else:
            self.platforms = [p for p in self.platforms if isinstance(p, str) and p.strip()]
            if not self.platforms:
                self.platforms = ["linkedin", "glassdoor"]


@dataclass
class SearchResult:
    """Result of a job search"""
    
    success: bool
    total_found: int
    total_unique: int
    total_duplicates: int
    total_analyzed: int
    jobs_saved: int
    errors: List[str]
    platform_results: Dict[str, int]
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "success": self.success,
            "total_found": self.total_found,
            "total_unique": self.total_unique,
            "total_duplicates": self.total_duplicates,
            "total_analyzed": self.total_analyzed,
            "jobs_saved": self.jobs_saved,
            "errors": self.errors,
            "platform_results": self.platform_results,
        }


class JobSearchService:
    """Main service for orchestrating job searches"""
    
    def __init__(self, db: Session):
        self.db = db
        self.deduplicator = get_deduplicator()
        self.analysis_service = get_job_analysis_service()
    
    async def search(self, config: SearchConfig) -> SearchResult:
        """
        Execute a job search across configured platforms.
        
        Args:
            config: Search configuration
        
        Returns:
            SearchResult with statistics
        """
        logger.info(f"Starting job search for candidate {config.candidate_id}: '{config.query}'")
        
        errors = []
        platform_results = {}
        all_jobs = []
        
        # Get candidate
        candidate = self.db.query(Candidate).filter(Candidate.id == config.candidate_id).first()
        if not candidate:
            return SearchResult(
                success=False,
                total_found=0,
                total_unique=0,
                total_duplicates=0,
                total_analyzed=0,
                jobs_saved=0,
                errors=[f"Candidate {config.candidate_id} not found"],
                platform_results={},
            )
        
        # Get candidate skills for AI analysis (current field: skill_name; legacy-safe fallback: skill)
        candidate_skills = []
        for s in candidate.skills:
            if not getattr(s, "is_enabled", True):
                continue
            skill_value = getattr(s, "skill_name", None) or getattr(s, "skill", None)
            if skill_value:
                candidate_skills.append(skill_value)
        
        # Search each platform
        for platform in config.platforms:
            try:
                logger.info(f"Searching {platform}...")
                
                if platform == "linkedin":
                    jobs = await self._search_linkedin(config, candidate)
                elif platform == "glassdoor":
                    jobs = await self._search_glassdoor(config, candidate)
                else:
                    logger.warning(f"Unknown platform: {platform}")
                    continue
                
                platform_results[platform] = len(jobs)
                all_jobs.extend(jobs)
                logger.info(f"Found {len(jobs)} jobs on {platform}")
                if len(jobs) == 0:
                    rate_status = get_rate_limiter().get_status(platform)
                    if not rate_status.get("allowed", True):
                        warnings_msg = (
                            f"{platform.capitalize()}: skipped by rate limiter - {rate_status.get('reason', 'blocked')}."
                        )
                        errors.append(warnings_msg)
                        continue
                    warnings_msg = (
                        f"{platform.capitalize()}: 0 jobs returned. "
                        "Possible causes: session expired/login wall, strict rate limits/cooldown, "
                        "or no matches for query/location."
                    )
                    errors.append(warnings_msg)
                
            except Exception as e:
                error_msg = f"{platform} search failed: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
                platform_results[platform] = 0
            
        
        total_found = len(all_jobs)
        
        # Deduplicate
        unique_jobs = self._deduplicate_jobs(all_jobs, config.candidate_id)
        total_unique = len(unique_jobs)
        total_duplicates = total_found - total_unique
        
        logger.info(f"Deduplication: {total_found} found -> {total_unique} unique ({total_duplicates} duplicates)")
        
        # Save to database
        jobs_saved = 0
        total_analyzed = 0
        
        for job_data in unique_jobs:
            try:
                # Create job record
                job = self._create_job_record(job_data, config.candidate_id)
                self.db.add(job)
                self.db.commit()
                self.db.refresh(job)
                jobs_saved += 1
                
                # AI analysis (if enabled)
                if config.analyze_with_ai and job.description:
                    try:
                        analysis = await self.analysis_service.analyze_job(
                            job.description,
                            candidate_skills,
                        )
                        
                        # Update job with analysis results
                        job.ai_remote_score = analysis.remote_score
                        self.db.commit()
                        total_analyzed += 1
                        
                        logger.info(
                            f"Job {job.id} analyzed: remote_score={analysis.remote_score}, "
                            f"recommendation={analysis.recommendation}"
                        )
                        
                    except Exception as e:
                        logger.error(f"AI analysis failed for job {job.id}: {e}")
                        # Continue without analysis
                
            except Exception as e:
                logger.error(f"Failed to save job: {e}")
                if jobs_saved > 0:
                    self.db.rollback()
        
        success = jobs_saved > 0 or total_found > 0
        
        return SearchResult(
            success=success,
            total_found=total_found,
            total_unique=total_unique,
            total_duplicates=total_duplicates,
            total_analyzed=total_analyzed,
            jobs_saved=jobs_saved,
            errors=errors,
            platform_results=platform_results,
        )
    
    async def _search_linkedin(self, config: SearchConfig, candidate: Candidate) -> List[dict]:
        """Search LinkedIn for jobs"""
        # Get cookies path
        cookies_path = self._get_cookies_path(candidate, "linkedin")
        self._ensure_cookies_file(candidate, "linkedin", cookies_path)
        
        async with LinkedInScraper(headless=config.headless) as scraper:
            jobs = await scraper.search_jobs(
                query=config.query,
                location=config.location,
                max_jobs=config.max_jobs_per_platform,
                cookies_path=str(cookies_path),
            )
            return [job.to_dict() for job in jobs]
    
    async def _search_glassdoor(self, config: SearchConfig, candidate: Candidate) -> List[dict]:
        """Search Glassdoor for jobs"""
        # Get cookies path
        cookies_path = self._get_cookies_path(candidate, "glassdoor")
        self._ensure_cookies_file(candidate, "glassdoor", cookies_path)
        
        async with GlassdoorScraper(headless=config.headless) as scraper:
            jobs = await scraper.search_jobs(
                query=config.query,
                location=config.location,
                max_jobs=config.max_jobs_per_platform,
                cookies_path=str(cookies_path),
            )
            return [job.to_dict() for job in jobs]
    
    def _deduplicate_jobs(self, jobs: List[dict], candidate_id: int) -> List[dict]:
        """Remove duplicate jobs"""
        # Get existing jobs for this candidate
        existing_jobs = self.db.query(Job).filter(Job.candidate_id == candidate_id).all()
        
        # Create temporary Job objects for comparison
        temp_jobs = []
        for job_data in jobs:
            temp_job = Job(
                title=job_data.get("title", ""),
                company=job_data.get("company", ""),
                location=job_data.get("location", ""),
                platform=job_data.get("platform", ""),
                platform_job_id=job_data.get("platform_job_id"),
                description_hash=job_data.get("description_hash"),
            )
            temp_jobs.append((temp_job, job_data))
        
        # Filter duplicates
        unique_jobs = []
        for temp_job, job_data in temp_jobs:
            # Check against existing jobs in database
            is_duplicate = False
            
            for existing in existing_jobs:
                is_dup, _ = self.deduplicator.is_duplicate(temp_job, existing)
                if is_dup:
                    is_duplicate = True
                    break
            
            # Also check against jobs we've already added in this batch
            if not is_duplicate:
                for added_job_data in unique_jobs:
                    added_temp = Job(
                        title=added_job_data.get("title", ""),
                        company=added_job_data.get("company", ""),
                        location=added_job_data.get("location", ""),
                    )
                    is_dup, _ = self.deduplicator.is_duplicate(temp_job, added_temp)
                    if is_dup:
                        is_duplicate = True
                        break
            
            if not is_duplicate:
                unique_jobs.append(job_data)
        
        return unique_jobs
    
    def _create_job_record(self, job_data: dict, candidate_id: int) -> Job:
        """Create a Job record from scraped data"""
        # Determine platform
        platform = job_data.get("platform", "unknown")
        
        # Get description storage path
        description_path = None
        if job_data.get("description"):
            candidate = self.db.query(Candidate).filter(Candidate.id == candidate_id).first()
            if candidate:
                desc_dir = Path(candidate.folder_path) / "job_descriptions"
                desc_dir.mkdir(parents=True, exist_ok=True)
                description_path = str(desc_dir / f"{job_data.get('platform_job_id', 'unknown')}.txt")
                
                # Save full description to file
                Path(description_path).write_text(job_data.get("description", ""))
        
        return Job(
            candidate_id=candidate_id,
            title=job_data.get("title", ""),
            company=job_data.get("company", ""),
            location=job_data.get("location", ""),
            platform=platform,
            platform_job_id=job_data.get("platform_job_id"),
            original_url=job_data.get("job_url"),
            description_hash=job_data.get("description_hash"),
            description_snippet=job_data.get("snippet"),
            description_path=description_path,
            posted_date=self._parse_posted_date(job_data.get("posted_date")),
        )
    
    def _get_cookies_path(self, candidate: Candidate, platform: str) -> Path:
        """Get the cookies file path for a candidate and platform"""
        return Path(f"data/cookies/{candidate.uuid}_{platform}.enc")

    def _ensure_cookies_file(self, candidate: Candidate, platform: str, cookies_path: Path) -> None:
        """
        Ensure encrypted cookie file exists for scraper compatibility.
        Falls back to DB-stored cookies from PlatformAccount.
        """
        if cookies_path.exists():
            return

        account = self.db.query(PlatformAccount).filter(
            PlatformAccount.candidate_id == candidate.id,
            PlatformAccount.platform == platform,
            PlatformAccount.status == "active",
        ).first()
        if not account or not account.cookies_encrypted:
            return

        try:
            encrypted_bytes = (
                account.cookies_encrypted
                if isinstance(account.cookies_encrypted, bytes)
                else str(account.cookies_encrypted).encode()
            )
            payload = decrypt_json(encrypted_bytes)
            cookies = payload.get("cookies", payload if isinstance(payload, list) else [])
            if not isinstance(cookies, list) or not cookies:
                return

            cookies_path.parent.mkdir(parents=True, exist_ok=True)
            cookies_path.write_bytes(encrypt_data(json.dumps(cookies)))
            logger.info(f"Restored {platform} cookies file from database for candidate {candidate.id}")
        except Exception as e:
            logger.warning(f"Could not restore {platform} cookies file from database: {e}")
    
    def _parse_posted_date(self, posted_date: Optional[str]) -> Optional[datetime]:
        """Parse posted date string to datetime"""
        if not posted_date:
            return None
        
        # Try various formats
        formats = [
            "%Y-%m-%d",
            "%d %b %Y",
            "%B %d, %Y",
            "%d/%m/%Y",
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(posted_date, fmt)
            except ValueError:
                continue
        
        # Handle relative dates (e.g., "2 days ago", "Just posted")
        posted_lower = posted_date.lower()
        if "just" in posted_lower or "today" in posted_lower:
            return datetime.now()
        
        # Try to extract number and unit
        import re
        match = re.search(r"(\d+)\s*(day|week|hour)s?\s*ago", posted_lower)
        if match:
            value = int(match.group(1))
            unit = match.group(2)
            
            from datetime import timedelta
            if unit == "day":
                return datetime.now() - timedelta(days=value)
            elif unit == "week":
                return datetime.now() - timedelta(weeks=value)
            elif unit == "hour":
                return datetime.now() - timedelta(hours=value)
        
        return None


async def run_job_search(
    db: Session,
    candidate_id: int,
    query: str,
    location: str = "",
    platforms: List[str] = None,
    max_jobs: int = 20,
    analyze: bool = True,
    headless: bool = False,
) -> SearchResult:
    """
    Convenience function to run a job search.
    
    Args:
        db: Database session
        candidate_id: Candidate ID to search for
        query: Search query
        location: Location filter
        platforms: List of platforms to search
        max_jobs: Max jobs per platform
        analyze: Whether to run AI analysis
        headless: Run browsers in headless mode
    
    Returns:
        SearchResult
    """
    config = SearchConfig(
        candidate_id=candidate_id,
        query=query,
        location=location,
        platforms=platforms or ["linkedin", "glassdoor"],
        max_jobs_per_platform=max_jobs,
        analyze_with_ai=analyze,
        headless=headless,
    )
    
    service = JobSearchService(db)
    return await service.search(config)
