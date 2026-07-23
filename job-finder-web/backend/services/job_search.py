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
from typing import Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.models.candidate import Candidate
from backend.models.job import Job, SearchRun, SearchRunJob
from backend.models.platform_account import PlatformAccount
from backend.security import decrypt_json, encrypt_data
from backend.services.job_analysis import get_job_analysis_service, CandidateProfile, JobAnalysis
from backend.services.job_deduplication import get_deduplicator, from_scraped_dict
from backend.services.job_scoring import score_job
from backend.services.job_llm_refinement import get_job_llm_refinement_service
from backend.services.rate_limiter import get_rate_limiter
from backend.services.search_lock import get_search_lock
from backend.services.scraper_health import record_search_result
from backend.scrapers.linkedin import LinkedInScraper
from backend.scrapers.glassdoor import GlassdoorScraper
from backend.scrapers.we_work_remotely import WeWorkRemotelyScraper

logger = logging.getLogger(__name__)


@dataclass
class SearchConfig:
    """Configuration for a job search"""
    
    candidate_id: int
    query: str
    run_name: Optional[str] = None
    location: str = ""
    platforms: List[str] = None
    max_jobs_per_platform: int = 20
    analyze_with_ai: bool = True
    refine_with_llm: bool = False
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
    search_run_id: Optional[int] = None
    
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
            "search_run_id": self.search_run_id,
        }


class JobSearchService:
    """Main service for orchestrating job searches"""
    
    def __init__(self, db: Session):
        self.db = db
        self.deduplicator = get_deduplicator()
        self.analysis_service = get_job_analysis_service()
        self._platform_skip_reasons: Dict[str, str] = {}
        self._platform_error_reasons: Dict[str, str] = {}
    
    async def search(
        self,
        config: SearchConfig,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> SearchResult:
        """
        Execute a job search across configured platforms.

        Owns the global search-lock precondition: only one search may run at a
        time, regardless of caller (route, background task, or test). Callers
        no longer need to check the lock themselves.

        Args:
            config: Search configuration
            progress_callback: Optional callable(message) for real-time progress reporting

        Returns:
            SearchResult with statistics
        """
        lock = get_search_lock()
        if not lock.acquire(blocking=False):
            msg = "Another job search is already in progress. Please wait."
            logger.info("Rejected job search for candidate %s: %s", config.candidate_id, msg)
            if progress_callback:
                progress_callback(msg)
            return SearchResult(
                success=False,
                total_found=0,
                total_unique=0,
                total_duplicates=0,
                total_analyzed=0,
                jobs_saved=0,
                errors=[msg],
                platform_results={},
            )
        try:
            return await self._execute_search(config, progress_callback)
        finally:
            lock.release()

    async def _execute_search(
        self,
        config: SearchConfig,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> SearchResult:
        """Run the search now that the caller holds the global search lock."""
        logger.info(f"Starting job search for candidate {config.candidate_id}: '{config.query}'")

        def emit(msg: str) -> None:
            if progress_callback:
                progress_callback(msg)

        errors = []
        platform_results = {}
        all_jobs = []

        # Get candidate
        candidate = self.db.query(Candidate).filter(Candidate.id == config.candidate_id).first()
        if not candidate:
            emit(f"Error: Candidate {config.candidate_id} not found")
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
        
        candidate_profile = CandidateProfile.from_candidate(candidate)

        search_run = self._create_search_run(config)
        
        emit(f"Starting search on {len(config.platforms)} platform(s): {', '.join(config.platforms)}")

        # Search each platform
        for platform in config.platforms:
            try:
                emit(f"--- Searching {platform.capitalize()} ---")
                logger.info(f"Searching {platform}...")

                if platform == "linkedin":
                    jobs = await self._search_linkedin(config, candidate, progress_callback=progress_callback)
                elif platform == "glassdoor":
                    jobs = await self._search_glassdoor(config, candidate, progress_callback=progress_callback)
                elif platform == WeWorkRemotelyScraper.platform:
                    jobs = await self._search_we_work_remotely(config, progress_callback=progress_callback)
                else:
                    logger.warning(f"Unknown platform: {platform}")
                    continue

                platform_results[platform] = len(jobs)
                all_jobs.extend(jobs)
                logger.info(f"Found {len(jobs)} jobs on {platform}")
                emit(f"{platform.capitalize()}: {len(jobs)} jobs collected")

                # Update scraper health tracker
                record_search_result(platform, len(jobs))

                if len(jobs) == 0:
                    skip_reason = self._platform_skip_reasons.get(platform)
                    if skip_reason is None and platform != "linkedin":
                        rate_status = get_rate_limiter().get_status(platform)
                        if not rate_status.get("allowed", True):
                            skip_reason = rate_status.get("reason", "blocked")
                    error_reason = self._platform_error_reasons.get(platform)
                    if skip_reason:
                        errors.append(f"{platform.capitalize()}: skipped by rate limiter - {skip_reason}.")
                        continue
                    if error_reason:
                        errors.append(f"{platform.capitalize()}: search failed - {error_reason}.")
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
                emit(f"Error on {platform}: {str(e)}")
                errors.append(error_msg)
                platform_results[platform] = 0
            
        
        total_found = len(all_jobs)
        emit(f"--- Post-processing {total_found} total jobs ---")

        # Deduplicate into candidate-level jobs while retaining every result as
        # a membership in this named run.  Known postings are sightings, not
        # discarded results.
        emit(f"Deduplicating {total_found} jobs...")
        memberships = self._plan_run_memberships(all_jobs, config.candidate_id)
        total_unique = len(memberships)
        total_duplicates = total_found - total_unique

        logger.info(f"Deduplication: {total_found} found -> {total_unique} run memberships ({total_duplicates} repeats merged)")
        emit(f"Deduplication: {total_unique} jobs in this saved list ({total_duplicates} repeated sightings merged)")

        # Save to database
        jobs_saved = 0
        total_analyzed = 0

        run_jobs = []
        for job_data, existing_job, sighted_platforms in memberships:
            try:
                first_sighting = existing_job is None
                job = existing_job or self._create_job_record(job_data, config.candidate_id)
                if first_sighting:
                    self.db.add(job)
                else:
                    self._refresh_job_from_sighting(job, job_data)
                self.db.commit()
                self.db.refresh(job)
                if first_sighting:
                    jobs_saved += 1
                emit(
                    f"Saved [{len(run_jobs) + 1}/{total_unique}]: "
                    f"{job_data.get('title', '?')} @ {job_data.get('company', '?')}"
                )

                # AI analysis (if enabled)
                if first_sighting and config.analyze_with_ai and job_data.get("description"):
                    try:
                        emit(f"Analyzing with AI: {job_data.get('title', '?')} @ {job_data.get('company', '?')}")
                        analysis = await self.analysis_service.analyze_job(
                            job_data.get("description"),
                            candidate_profile,
                            db=self.db,
                            platform_remote_attribute=job_data.get("remote_attribute"),
                        )

                        # Update job with analysis results
                        job.ai_remote_score = analysis.remote_score
                        job.verified_remote_status = analysis.verified_remote_status
                        job.remote_restrictions = (
                            json.dumps(analysis.remote_restrictions, sort_keys=True)
                            if analysis.remote_restrictions else None
                        )
                        job.remote_evidence = (
                            json.dumps(analysis.remote_evidence)
                            if analysis.remote_evidence else None
                        )
                        job.remote_verified_version = analysis.remote_verified_version
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
                continue

            run_jobs.append((job, first_sighting, sighted_platforms))

        # This intentionally happens after all jobs receive their deterministic
        # scores.  The optional LLM stage only sees the deterministic top-N and
        # stores a companion score; it cannot influence default result ordering.
        if config.refine_with_llm:
            try:
                refined = await get_job_llm_refinement_service(self.db).refine_top_jobs(candidate)
                if refined:
                    emit(f"Refined {refined} top deterministic matches with AI")
            except Exception as e:
                logger.error("LLM top-N refinement failed: %s", e)

        # Snapshot only after optional scoring/refinement has completed.  The
        # saved list must keep these values even if the live Job is later
        # rescored or reverified.
        for job, first_sighting, sighted_platforms in run_jobs:
            self.db.add(self._create_run_membership(
                search_run, job, first_sighting, sighted_platforms,
            ))
        search_run.finished_at = datetime.utcnow()
        self.db.commit()
        
        success = jobs_saved > 0 or total_found > 0
        emit(
            f"Search complete! {jobs_saved} jobs saved"
            + (f", {total_analyzed} analyzed with AI" if total_analyzed else "")
            + (f". Errors: {len(errors)}" if errors else ".")
        )

        return SearchResult(
            success=success,
            total_found=total_found,
            total_unique=total_unique,
            total_duplicates=total_duplicates,
            total_analyzed=total_analyzed,
            jobs_saved=jobs_saved,
            errors=errors,
            platform_results=platform_results,
            search_run_id=search_run.id,
        )
    
    async def _search_linkedin(
        self,
        config: SearchConfig,
        candidate: Candidate,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> List[dict]:
        """Search LinkedIn for jobs"""
        cookies_path = self._get_cookies_path(candidate, "linkedin")
        self._ensure_cookies_file(candidate, "linkedin", cookies_path)
        from backend.services.rate_limiter import normalize_linkedin_settings
        account = self._get_platform_account(candidate, "linkedin")
        try:
            settings = normalize_linkedin_settings(json.loads(account.rate_limit_settings) if account and account.rate_limit_settings else {})
        except (TypeError, ValueError):
            settings = normalize_linkedin_settings({})

        if account and account.status in ("expired", "captcha_required"):
            from backend.routes.platform_accounts import _account_guidance
            reason = _account_guidance(account)["label"]
            if progress_callback:
                progress_callback(
                    f"LinkedIn: Skipped — {reason}. Re-login on the account page before searching."
                )
            return []

        async with LinkedInScraper(headless=config.headless) as scraper:
            jobs = await scraper.search_jobs(
                query=config.query,
                location=config.location,
                max_jobs=config.max_jobs_per_platform,
                cookies_path=str(cookies_path),
                rate_limit_scope=f"linkedin:{candidate.id}",
                rate_limit_settings=settings,
                manual_session_key=f"{candidate.uuid}:linkedin",
                manual_profile_path=str(cookies_path.parent.parent / "browser-login-profiles" / f"{candidate.uuid}_linkedin"),
                progress_callback=progress_callback,
            )
            self._apply_scraper_outcome(scraper, account, "linkedin")
            return [{**job.to_dict(), "platform": "linkedin"} for job in jobs]

    async def _search_glassdoor(
        self,
        config: SearchConfig,
        candidate: Candidate,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> List[dict]:
        """Search Glassdoor for jobs"""
        cookies_path = self._get_cookies_path(candidate, "glassdoor")
        self._ensure_cookies_file(candidate, "glassdoor", cookies_path)
        account = self._get_platform_account(candidate, "glassdoor")

        async with GlassdoorScraper(headless=config.headless) as scraper:
            jobs = await scraper.search_jobs(
                query=config.query,
                location=config.location,
                max_jobs=config.max_jobs_per_platform,
                cookies_path=str(cookies_path),
                progress_callback=progress_callback,
            )
            self._apply_scraper_outcome(scraper, account, "glassdoor")
            return [{**job.to_dict(), "platform": "glassdoor"} for job in jobs]

    async def _search_we_work_remotely(
        self,
        config: SearchConfig,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> List[dict]:
        """Run the WWR adapter, which rejects live access until R3 is authorized.

        Keeping this dispatch path explicit makes WWR selectable in a search
        configuration while ensuring an unapproved selection cannot silently
        fall through to browser or network activity.
        """
        jobs = await WeWorkRemotelyScraper().search_jobs(
            query=config.query,
            location=config.location,
            max_jobs=config.max_jobs_per_platform,
            progress_callback=progress_callback,
        )
        return [{**job.to_dict(), "platform": WeWorkRemotelyScraper.platform} for job in jobs]

    def _get_platform_account(self, candidate: Candidate, platform: str) -> Optional[PlatformAccount]:
        return self.db.query(PlatformAccount).filter(
            PlatformAccount.candidate_id == candidate.id,
            PlatformAccount.platform == platform,
        ).first()

    def _apply_scraper_outcome(self, scraper, account: Optional[PlatformAccount], platform: str) -> None:
        """Record a scraper's session outcome uniformly across platforms.

        Every JobPlatformAdapter reports outcome via ScraperSessionState
        attributes instead of raising, so this is the one place that turns
        those attributes into skip/error reasons and account status.
        """
        if scraper.rate_limited_reason:
            self._platform_skip_reasons[platform] = scraper.rate_limited_reason
        elif scraper.last_error:
            self._platform_error_reasons[platform] = scraper.last_error
        if not account:
            return
        if scraper.manual_challenge_handoff:
            account.status = "captcha_required"
            self.db.commit()
        elif scraper.login_wall_detected:
            account.status = "expired"
            self.db.commit()

    def _create_search_run(self, config: SearchConfig) -> SearchRun:
        """Persist a list header before collecting results for it."""
        default_name = f"{datetime.utcnow():%Y-%m-%d} — {config.query.strip() or 'Job search'}"
        search_run = SearchRun(
            candidate_id=config.candidate_id,
            name=(config.run_name or "").strip() or default_name,
            query=config.query,
            location=config.location,
            platforms=json.dumps(config.platforms, sort_keys=True),
        )
        self.db.add(search_run)
        self.db.commit()
        self.db.refresh(search_run)
        return search_run

    def _plan_run_memberships(self, jobs: List[dict], candidate_id: int):
        """Match scraped postings to a job, merging only duplicate sightings."""
        existing_jobs = self.db.query(Job).filter(Job.candidate_id == candidate_id).all()
        planned = []
        for job_data in jobs:
            temp_job = from_scraped_dict(job_data)
            matched_job = next((job for job in existing_jobs if self.deduplicator.is_duplicate(temp_job, job)[0]), None)
            matching_plan = None
            if matched_job is None:
                for plan in planned:
                    planned_temp = from_scraped_dict(plan[0])
                    if self.deduplicator.is_duplicate(temp_job, planned_temp)[0]:
                        matching_plan = plan
                        break
            if matching_plan is not None:
                platform = job_data.get("platform")
                if platform and platform not in matching_plan[2]:
                    matching_plan[2].append(platform)
            else:
                planned.append([job_data, matched_job, [job_data.get("platform")] if job_data.get("platform") else []])
        return planned

    @staticmethod
    def _refresh_job_from_sighting(job: Job, job_data: dict) -> None:
        """Refresh safe volatile source details without changing job identity."""
        for field, source_key in (("salary", "salary"), ("original_url", "job_url"), ("location", "location")):
            value = job_data.get(source_key)
            if value:
                setattr(job, field, value)

    @staticmethod
    def _create_run_membership(search_run, job, first_sighting, sighted_platforms) -> SearchRunJob:
        return SearchRunJob(
            search_run_id=search_run.id, job_id=job.id, first_sighting=first_sighting,
            sighted_platforms=json.dumps(sighted_platforms, sort_keys=True),
            deterministic_score=job.deterministic_score, scoring_version=job.scoring_version,
            llm_score=job.llm_score, llm_prompt_version=job.llm_prompt_version,
            verified_remote_status=job.verified_remote_status,
            remote_verified_version=job.remote_verified_version, salary=job.salary,
        )
    
    def _create_job_record(self, job_data: dict, candidate_id: int) -> Job:
        """Create a Job record from scraped data"""
        # Determine platform
        platform = job_data.get("platform", "unknown")
        
        # Get description storage path
        candidate = self.db.query(Candidate).filter(Candidate.id == candidate_id).first()
        preferred_titles = candidate.active_titles() if candidate else []
        candidate_skills = candidate.active_skill_names() if candidate else []
        score = score_job(
            job_data.get("title"),
            job_data.get("description") or job_data.get("snippet"),
            preferred_titles,
            candidate_skills,
        )

        description_path = None
        if job_data.get("description"):
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
            salary=job_data.get("salary"),
            description_hash=job_data.get("description_hash"),
            description_snippet=job_data.get("snippet"),
            description_path=description_path,
            deterministic_score=score.composite_score,
            score_breakdown=json.dumps(score.as_dict(), sort_keys=True),
            scoring_version=score.scoring_version,
            posted_date=self._parse_posted_date(job_data.get("posted_date")),
        )
    
    def _get_cookies_path(self, candidate: Candidate, platform: str) -> Path:
        """Get the cookies file path for a candidate and platform"""
        from backend.config import DATA_DIR
        return DATA_DIR / "cookies" / f"{candidate.uuid}_{platform}.enc"

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
            cookies_path.write_text(encrypt_data(json.dumps(cookies)))
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
    run_name: Optional[str] = None,
    location: str = "",
    platforms: List[str] = None,
    max_jobs: int = 20,
    analyze: bool = True,
    headless: bool = False,
    progress_callback: Optional[Callable[[str], None]] = None,
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
        progress_callback: Optional callable(message) for real-time progress

    Returns:
        SearchResult
    """
    config = SearchConfig(
        candidate_id=candidate_id,
        query=query,
        run_name=run_name,
        location=location,
        platforms=platforms or ["linkedin", "glassdoor"],
        max_jobs_per_platform=max_jobs,
        analyze_with_ai=analyze,
        headless=headless,
    )

    service = JobSearchService(db)
    return await service.search(config, progress_callback=progress_callback)
