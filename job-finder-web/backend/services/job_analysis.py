"""
AI Job Analysis Service

Analyzes job postings using LLM to determine:
- Remote work compatibility score (0-100)
- Armenia compatibility (timezone, citizenship, relocation)
- Skill match analysis
- Red flags detection
"""
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

from sqlalchemy.orm import Session

from backend.ai_capabilities import Purpose
from backend.services.llm_service import send_message

logger = logging.getLogger(__name__)

REMOTE_VERIFICATION_PROMPT_VERSION = "remote-verification-v1"
REMOTE_STATUSES = {"fully_remote", "remote_restricted", "hybrid", "onsite", "unknown"}


@dataclass
class CandidateProfile:
    """The candidate fields that personalize a job analysis prompt and cache key."""

    skills: List[str]
    location: Optional[str] = None
    timezone: Optional[str] = None
    experience_years: Optional[int] = None
    current_role: Optional[str] = None
    target_roles: Optional[List[str]] = None

    @classmethod
    def from_candidate(cls, candidate) -> "CandidateProfile":
        """Derive the analysis profile from a Candidate ORM row.

        The single seam that turns a persisted candidate into the fields that
        personalize the prompt and cache key. Reads active skills/titles through
        the candidate's own canonical accessors so soft-deleted or disabled
        entries never reach the analysis.
        """
        return cls(
            skills=candidate.active_skill_names(),
            location=candidate.location,
            timezone=candidate.timezone,
            experience_years=candidate.experience_years,
            current_role=candidate.current_role,
            target_roles=candidate.active_titles(),
        )

    def cache_key(self) -> str:
        """Identity string for cache invalidation. Empty when no profile fields are set."""
        if not any([
            self.location, self.timezone, self.experience_years,
            self.current_role, self.target_roles,
        ]):
            return ""
        return "|".join([
            self.location or "",
            self.timezone or "",
            str(self.experience_years or ""),
            self.current_role or "",
            ",".join(sorted(self.target_roles)) if self.target_roles else "",
        ])

    def experience_text(self) -> str:
        if self.experience_years and self.current_role:
            return f"{self.experience_years}+ years, currently {self.current_role}"
        if self.experience_years:
            return f"{self.experience_years}+ years"
        if self.current_role:
            return f"Currently {self.current_role}"
        return "Not specified"


@dataclass
class JobAnalysis:
    """Result of AI job analysis"""
    
    # Remote work score (0-100)
    remote_score: int
    
    # Remote work type
    remote_type: str  # "Fully Remote", "Hybrid", "Onsite", "Unknown"
    
    # Location requirements
    location_requirement: str  # "Worldwide", "US Only", "EU Only", "Specific Country", etc.
    
    # Citizenship/visa requirements
    citizenship_required: Optional[str]  # "US", "EU", None
    
    # Office visits required
    office_visits: str  # "Never", "Occasional", "Regular", "Unknown"
    
    # Timezone requirements
    timezone_requirement: Optional[str]
    
    # Skill match
    matched_skills: List[str]
    missing_skills: List[str]
    skill_match_score: int  # 0-100
    
    # Experience level
    experience_level: str  # "Entry", "Mid", "Senior", "Staff", "Principal"
    
    # Red flags
    red_flags: List[str]
    
    # Summary
    summary: str
    
    # Recommendation
    recommendation: str  # "Apply", "Consider", "Skip"

    # R6's persisted, canonical remote shape.  Defaults retain compatibility
    # with cached analyses from before verification was introduced.
    verified_remote_status: str = "unknown"
    remote_restrictions: Optional[dict] = None
    remote_evidence: Optional[dict] = None
    remote_verified_version: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "remote_score": self.remote_score,
            "remote_type": self.remote_type,
            "location_requirement": self.location_requirement,
            "citizenship_required": self.citizenship_required,
            "office_visits": self.office_visits,
            "timezone_requirement": self.timezone_requirement,
            "matched_skills": self.matched_skills,
            "missing_skills": self.missing_skills,
            "skill_match_score": self.skill_match_score,
            "experience_level": self.experience_level,
            "red_flags": self.red_flags,
            "summary": self.summary,
            "recommendation": self.recommendation,
            "verified_remote_status": self.verified_remote_status,
            "remote_restrictions": self.remote_restrictions,
            "remote_evidence": self.remote_evidence,
            "remote_verified_version": self.remote_verified_version,
        }


# System prompt for job analysis
JOB_ANALYSIS_PROMPT = """
You are an expert job analyst specializing in remote work compatibility assessment.
Analyze the following job posting and provide a structured assessment.

**Candidate Profile:**
- Location: {candidate_location} ({candidate_timezone} timezone)
- Experience: {candidate_experience}
- Target Roles: {candidate_target_roles}

**Analysis Tasks:**

1. **Remote Work Score (0-100):**
   - 40 points: Fully remote (no office required)
   - 25 points: Location flexibility (worldwide vs country-specific)
   - 20 points: No citizenship/visa restrictions
   - 15 points: No office visits required
   
2. **Candidate Location Compatibility:**
   - Check for timezone overlap requirements
   - Check for citizenship/visa restrictions
   - Check for relocation requirements
   - Check for occasional/regular office visits

3. **Skill Match:**
   - Compare job requirements with candidate's skills
   - Identify matched and missing skills
   - Calculate skill match percentage

4. **Red Flags:**
   - "US citizens only" or similar restrictions
   - "Must relocate" requirements
   - "Onsite required" statements
   - Excessive experience requirements (20+ years)
   - Salary range below market

**Output Format:**
Provide your analysis in valid JSON format with this exact structure:

{{
  "remote_score": <integer 0-100>,
  "remote_type": "<Fully Remote|Hybrid|Onsite|Unknown>",
  "location_requirement": "<Worldwide|US Only|EU Only|Specific Country|...>",
  "citizenship_required": "<US|EU|...|null>",
  "office_visits": "<Never|Occasional|Regular|Unknown>",
  "timezone_requirement": "<string or null>",
  "matched_skills": ["skill1", "skill2", ...],
  "missing_skills": ["skill1", "skill2", ...],
  "skill_match_score": <integer 0-100>,
  "experience_level": "<Entry|Mid|Senior|Staff|Principal>",
  "red_flags": ["flag1", "flag2", ...],
  "summary": "<2-3 sentence summary>",
  "recommendation": "<Apply|Consider|Skip>"
  ,"verified_remote_status": "<fully_remote|remote_restricted|hybrid|onsite|unknown>",
  "remote_restrictions": {{"regions": ["US"], "citizenship": null, "timezone_overlap": null, "office_visits": "<never|occasional|regular|unknown>"}},
  "remote_evidence": ["<exact quote from the job posting>"]
}}

**Job Posting:**
{job_description}

**Candidate Skills:**
{candidate_skills}

Provide ONLY the JSON output, no additional text.
"""


class JobAnalysisService:
    """Service for AI-powered job analysis"""
    
    def __init__(self):
        from backend.config import DATA_DIR
        self._cache_dir = DATA_DIR / "job_analysis_cache"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_key(self, description: str, skills: List[str], candidate_profile_key: str = "") -> str:
        """Generate cache key from description, skills, and candidate profile identity"""
        content = f"{description}|||{','.join(sorted(skills))}|||{candidate_profile_key}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """Get cache file path"""
        return self._cache_dir / f"{cache_key}.json"
    
    def _load_from_cache(self, cache_key: str) -> Optional[JobAnalysis]:
        """Load analysis from cache if available"""
        cache_path = self._get_cache_path(cache_key)
        if cache_path.exists():
            try:
                data = json.loads(cache_path.read_text())
                return JobAnalysis(**data)
            except Exception as e:
                logger.warning(f"Failed to load cached analysis: {e}")
        return None
    
    def _save_to_cache(self, cache_key: str, analysis: JobAnalysis):
        """Save analysis to cache"""
        cache_path = self._get_cache_path(cache_key)
        cache_path.write_text(json.dumps(analysis.to_dict(), indent=2))
        logger.debug(f"Cached job analysis: {cache_key}")
    
    async def analyze_job(
        self,
        job_description: str,
        candidate: CandidateProfile,
        use_cache: bool = True,
        model_name: Optional[str] = None,
        db: Optional[Session] = None,
        platform_remote_attribute: Optional[str] = None,
    ) -> JobAnalysis:
        """
        Analyze a job posting using AI.

        Args:
            job_description: Full job description text
            candidate: The candidate profile personalizing this analysis
            use_cache: Whether to use cached results
            model_name: Optional model override
            platform_remote_attribute: Platform's own remote-work claim, if any

        Returns:
            JobAnalysis object with detailed assessment
        """
        # Missing text cannot be verified; avoid an unnecessary provider call.
        if not job_description or not job_description.strip():
            return JobAnalysis(
                remote_score=0, remote_type="Unknown", location_requirement="Unknown",
                citizenship_required=None, office_visits="Unknown", timezone_requirement=None,
                matched_skills=[], missing_skills=[], skill_match_score=0,
                experience_level="Unknown", red_flags=[], summary="No job description available.",
                recommendation="Consider", verified_remote_status="unknown",
                remote_verified_version=REMOTE_VERIFICATION_PROMPT_VERSION,
            )

        # Check cache
        # The platform claim affects whether evidence is required, so it is
        # part of the cached verification identity.
        cache_description = job_description
        if platform_remote_attribute:
            cache_description = f"{job_description}|||platform-remote:{platform_remote_attribute}"
        # The candidate's profile shapes the prompt, so it is part of the
        # cached analysis identity too. Empty when no profile fields are set,
        # so callers with a bare-skills profile keep the pre-existing key.
        cache_key = self._get_cache_key(cache_description, candidate.skills, candidate.cache_key())
        if use_cache:
            cached = self._load_from_cache(cache_key)
            if cached:
                logger.info("Using cached job analysis")
                return cached

        # Prepare prompt
        prompt = JOB_ANALYSIS_PROMPT.format(
            job_description=job_description[:8000],  # Truncate if too long
            candidate_skills=", ".join(candidate.skills) if candidate.skills else "Not provided",
            candidate_location=candidate.location or "Not specified",
            candidate_timezone=candidate.timezone or "Not specified",
            candidate_experience=candidate.experience_text(),
            candidate_target_roles=", ".join(candidate.target_roles) if candidate.target_roles else "Not specified",
        )
        
        # Call LLM
        try:
            logger.info(f"Analyzing job with LLM (model: {model_name or 'default'})...")
            response = await send_message(
                prompt,
                model_override=model_name,
                temperature=0.1,  # Low temperature for consistent analysis
                db=db,
                routing_purpose=Purpose.CANDIDATE_ANALYSIS,
            )
            
            # Parse JSON response
            # Remove markdown code blocks if present
            response_text = response.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            data = json.loads(response_text)
            
            # Create JobAnalysis object
            analysis = JobAnalysis(
                remote_score=data.get("remote_score", 50),
                remote_type=data.get("remote_type", "Unknown"),
                location_requirement=data.get("location_requirement", "Unknown"),
                citizenship_required=data.get("citizenship_required"),
                office_visits=data.get("office_visits", "Unknown"),
                timezone_requirement=data.get("timezone_requirement"),
                matched_skills=data.get("matched_skills", []),
                missing_skills=data.get("missing_skills", []),
                skill_match_score=data.get("skill_match_score", 50),
                experience_level=data.get("experience_level", "Mid"),
                red_flags=data.get("red_flags", []),
                summary=data.get("summary", ""),
                recommendation=data.get("recommendation", "Consider"),
            )
            self._canonicalize_remote_verification(
                analysis, job_description, platform_remote_attribute,
                raw_restrictions=data.get("remote_restrictions"),
                raw_evidence=data.get("remote_evidence"),
                raw_status=data.get("verified_remote_status"),
            )
            
            # Save to cache
            if use_cache:
                self._save_to_cache(cache_key, analysis)
            
            logger.info(f"Job analysis complete: remote_score={analysis.remote_score}, recommendation={analysis.recommendation}")
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze job: {e}")
            # Return a default analysis on failure
            return JobAnalysis(
                remote_score=0,
                remote_type="Unknown",
                location_requirement="Unknown",
                citizenship_required=None,
                office_visits="Unknown",
                timezone_requirement=None,
                matched_skills=[],
                missing_skills=[],
                skill_match_score=50,
                experience_level="Mid",
                red_flags=[f"Analysis failed: {str(e)}"],
                summary="Job analysis failed. Please review manually.",
                recommendation="Consider",
                verified_remote_status="unknown",
                remote_verified_version=REMOTE_VERIFICATION_PROMPT_VERSION,
            )

    def _canonicalize_remote_verification(
        self,
        analysis: JobAnalysis,
        description: str,
        platform_remote_attribute: Optional[str],
        raw_restrictions: Any,
        raw_evidence: Any,
        raw_status: Any,
    ) -> None:
        """Make LLM remote data safe to persist without guessing on failures."""
        if not description or not description.strip():
            analysis.verified_remote_status = "unknown"
            analysis.remote_restrictions = None
            analysis.remote_evidence = None
            analysis.remote_verified_version = REMOTE_VERIFICATION_PROMPT_VERSION
            analysis.remote_score = 0
            return

        restrictions = self._normalize_restrictions(raw_restrictions, analysis)
        status = str(raw_status or "").strip().lower()
        provider_supplied_status = status in REMOTE_STATUSES
        if not provider_supplied_status:
            status = self._status_from_legacy_analysis(analysis, restrictions)
        if restrictions and status == "fully_remote":
            status = "remote_restricted"
        quotes = self._verbatim_evidence(raw_evidence, description)
        # A platform remote claim contradicted by the text must retain an exact
        # quote; otherwise verification is deliberately unknown, never guessed.
        contradiction = self._claims_remote(platform_remote_attribute) and status in {"remote_restricted", "hybrid", "onsite"}
        if contradiction and not quotes:
            status = "unknown"
            restrictions = None
        analysis.verified_remote_status = status
        analysis.remote_restrictions = restrictions if status == "remote_restricted" else None
        # A contradiction records both the platform claim and exact source
        # spans, so a later UI never presents an LLM paraphrase as evidence.
        analysis.remote_evidence = (
            {"platform_attribute": platform_remote_attribute, "description_quotes": quotes}
            if contradiction and quotes else None
        )
        analysis.remote_verified_version = REMOTE_VERIFICATION_PROMPT_VERSION
        # Old cached/provider responses have no canonical status.  Keep their
        # historical convenience score while persisting the canonical fields;
        # R6-shaped responses derive the convenience score from the enum.
        if provider_supplied_status:
            analysis.remote_score = self._score_for_status(status)

    @staticmethod
    def _claims_remote(attribute: Optional[str]) -> bool:
        return bool(attribute and str(attribute).strip().lower() in {"remote", "fully_remote", "fully remote"})

    @staticmethod
    def _verbatim_evidence(value: Any, description: str) -> list:
        values = value if isinstance(value, list) else [value] if isinstance(value, str) else []
        return [quote.strip() for quote in values if quote and quote.strip() in description]

    @staticmethod
    def _normalize_restrictions(value: Any, analysis: JobAnalysis) -> Optional[dict]:
        source = value if isinstance(value, dict) else {}
        region_map = {"united states": "US", "usa": "US", "us": "US", "european union": "EU", "eu": "EU"}
        regions = source.get("regions", [])
        if isinstance(regions, str):
            regions = [regions]
        normalized_regions = [region_map.get(str(region).strip().lower(), str(region).strip().upper()) for region in regions if str(region).strip()]
        citizenship = source.get("citizenship") or analysis.citizenship_required
        timezone = source.get("timezone_overlap") or analysis.timezone_requirement
        visits = str(source.get("office_visits") or analysis.office_visits or "unknown").strip().lower()
        visits = {"never": "never", "occasional": "occasional", "regular": "regular"}.get(visits, "unknown")
        result = {"regions": normalized_regions, "citizenship": citizenship, "timezone_overlap": timezone, "office_visits": visits}
        return result if normalized_regions or citizenship or timezone or visits != "unknown" else None

    @staticmethod
    def _status_from_legacy_analysis(analysis: JobAnalysis, restrictions: Optional[dict]) -> str:
        remote_type = (analysis.remote_type or "").strip().lower()
        if "onsite" in remote_type:
            return "onsite"
        if "hybrid" in remote_type:
            return "hybrid"
        if restrictions:
            return "remote_restricted"
        if "fully" in remote_type or remote_type == "remote":
            return "fully_remote"
        return "unknown"

    @staticmethod
    def _score_for_status(status: str) -> int:
        return {"fully_remote": 100, "remote_restricted": 60, "hybrid": 35, "onsite": 0, "unknown": 0}[status]
    
    def calculate_armenia_compatibility(self, analysis: JobAnalysis) -> tuple[bool, List[str]]:
        """
        Determine if a job is compatible with working from Armenia.
        
        Returns:
            (is_compatible, list_of_issues)
        """
        issues = []
        
        # Check citizenship requirements
        if analysis.citizenship_required:
            if analysis.citizenship_required.lower() in ["us", "usa", "united states"]:
                issues.append("US citizenship required")
            elif analysis.citizenship_required.lower() in ["eu", "european union"]:
                issues.append("EU citizenship required")
        
        # Check location requirements
        location_lower = analysis.location_requirement.lower()
        if "us only" in location_lower or "united states only" in location_lower:
            issues.append("Location restricted to United States")
        elif "relocate" in location_lower:
            issues.append("Relocation required")
        
        # Check office visits
        if analysis.office_visits in ["Regular", "Onsite"]:
            issues.append(f"Office visits: {analysis.office_visits}")
        
        # Check timezone
        if analysis.timezone_requirement:
            tz_lower = analysis.timezone_requirement.lower()
            if "us" in tz_lower and ("pst" in tz_lower or "est" in tz_lower):
                # Check if significant overlap is required
                if "business hours" in tz_lower or "9am" in tz_lower or "9 am" in tz_lower:
                    issues.append(f"Timezone requirement: {analysis.timezone_requirement}")
        
        # Check red flags
        for flag in analysis.red_flags:
            flag_lower = flag.lower()
            if any(keyword in flag_lower for keyword in ["citizen", "relocate", "onsite", "visa"]):
                issues.append(f"Red flag: {flag}")
        
        is_compatible = len(issues) == 0
        return is_compatible, issues
    
    def clear_cache(self, older_than_days: int = 7):
        """Clear cached analyses older than specified days"""
        from datetime import timedelta
        
        cutoff = datetime.now() - timedelta(days=older_than_days)
        cleared = 0
        
        for cache_file in self._cache_dir.glob("*.json"):
            mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
            if mtime < cutoff:
                cache_file.unlink()
                cleared += 1
        
        if cleared > 0:
            logger.info(f"Cleared {cleared} cached job analyses")
        return cleared


# Global instance
_job_analysis_service: Optional[JobAnalysisService] = None


def get_job_analysis_service() -> JobAnalysisService:
    """Get or create the job analysis service"""
    global _job_analysis_service
    if _job_analysis_service is None:
        _job_analysis_service = JobAnalysisService()
    return _job_analysis_service
