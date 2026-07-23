"""
Job Deduplication Service

Prevents duplicate job listings from appearing in search results.
Uses multi-signal matching with calibrated thresholds:
- Job title similarity
- Company name similarity
- Location similarity
- Description hash (exact duplicates)
- Platform job ID (if available)
"""
import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

from fuzzywuzzy import fuzz

from backend.models.job import Job

logger = logging.getLogger(__name__)


@dataclass
class DeduplicationSignal:
    """Signals used for deduplication matching"""
    
    # Exact matches
    description_hash_match: bool = False
    platform_job_id_match: bool = False
    
    # Fuzzy matches (0-100)
    title_similarity: int = 0
    company_similarity: int = 0
    location_similarity: int = 0
    
    # Combined score (0-100)
    combined_score: int = 0


# Deduplication thresholds
THRESHOLD_EXACT_MATCH = 95  # Definitely the same job
THRESHOLD_LIKELY_MATCH = 80  # Probably the same job
THRESHOLD_POSSIBLE_MATCH = 60  # Might be the same job

# The only fields JobDeduplicator.calculate_similarity reads. A transient
# comparison Job (see from_scraped_dict) only needs to populate these —
# adding a field here without a matching signal in calculate_similarity
# (or vice versa) breaks that contract.
DEDUP_IDENTITY_FIELDS = (
    "title", "company", "location", "platform", "platform_job_id", "description_hash",
)


class JobDeduplicator:
    """Service for detecting and preventing duplicate jobs"""
    
    def __init__(self):
        pass
    
    def compute_description_hash(self, description: str) -> str:
        """Compute a hash of the job description for exact duplicate detection"""
        # Normalize description before hashing
        normalized = " ".join(description.lower().split())
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def compute_description_snippet(self, description: str, max_length: int = 500) -> str:
        """Extract a snippet from the description for quick comparison"""
        # Remove extra whitespace
        cleaned = " ".join(description.split())
        return cleaned[:max_length]
    
    def calculate_similarity(self, job1: Job, job2: Job) -> DeduplicationSignal:
        """
        Calculate similarity between two jobs.
        
        Returns:
            DeduplicationSignal with match scores
        """
        signal = DeduplicationSignal()
        
        # Check exact matches first
        if job1.description_hash and job2.description_hash:
            signal.description_hash_match = job1.description_hash == job2.description_hash
        
        if job1.platform_job_id and job2.platform_job_id and job1.platform == job2.platform:
            signal.platform_job_id_match = job1.platform_job_id == job2.platform_job_id
        
        # Calculate fuzzy similarities
        signal.title_similarity = fuzz.ratio(job1.title.lower(), job2.title.lower())
        signal.company_similarity = fuzz.ratio(job1.company.lower(), job2.company.lower())
        
        if job1.location and job2.location:
            signal.location_similarity = fuzz.ratio(job1.location.lower(), job2.location.lower())
        else:
            signal.location_similarity = 50  # Neutral if missing
        
        # Calculate combined score
        signal.combined_score = self._calculate_combined_score(signal)
        
        return signal
    
    def _calculate_combined_score(self, signal: DeduplicationSignal) -> int:
        """
        Calculate combined match score from individual signals.
        
        Weights:
        - Description hash match: 100 (exact match)
        - Platform job ID match: 100 (exact match)
        - Title similarity: 40%
        - Company similarity: 40%
        - Location similarity: 20%
        """
        # Exact matches override everything
        if signal.description_hash_match or signal.platform_job_id_match:
            return 100
        
        # Weighted average of fuzzy matches
        title_weight = 0.4
        company_weight = 0.4
        location_weight = 0.2
        
        combined = int(
            signal.title_similarity * title_weight +
            signal.company_similarity * company_weight +
            signal.location_similarity * location_weight
        )
        
        return combined
    
    def is_duplicate(
        self,
        new_job: Job,
        existing_job: Job,
        threshold: int = THRESHOLD_LIKELY_MATCH
    ) -> Tuple[bool, DeduplicationSignal]:
        """
        Check if a new job is a duplicate of an existing job.
        
        Args:
            new_job: The new job to check
            existing_job: An existing job to compare against
            threshold: Minimum score to consider duplicate (default: 80)
        
        Returns:
            (is_duplicate, signal) tuple
        """
        signal = self.calculate_similarity(new_job, existing_job)
        is_dup = signal.combined_score >= threshold
        
        if is_dup:
            logger.debug(
                f"Duplicate detected: '{new_job.title}' at {new_job.company} "
                f"matches '{existing_job.title}' at {existing_job.company} "
                f"(score: {signal.combined_score})"
            )
        
        return is_dup, signal
    
    def filter_duplicates(
        self,
        new_jobs: List[Job],
        existing_jobs: List[Job],
        threshold: int = THRESHOLD_LIKELY_MATCH
    ) -> List[Job]:
        """
        Filter out duplicates from a list of new jobs.
        
        Args:
            new_jobs: List of new jobs to filter
            existing_jobs: List of existing jobs to compare against
            threshold: Minimum score to consider duplicate
        
        Returns:
            List of unique jobs (duplicates removed)
        """
        # Build a set of existing description hashes for fast lookup
        existing_hashes = {job.description_hash for job in existing_jobs if job.description_hash}
        existing_platform_ids = {
            (job.platform, job.platform_job_id)
            for job in existing_jobs
            if job.platform_job_id
        }
        
        unique_jobs = []
        
        for new_job in new_jobs:
            # Fast path: check description hash
            if new_job.description_hash and new_job.description_hash in existing_hashes:
                logger.debug(f"Filtered duplicate (hash): {new_job.title} at {new_job.company}")
                continue
            
            # Fast path: check platform job ID
            if (new_job.platform, new_job.platform_job_id) in existing_platform_ids:
                logger.debug(f"Filtered duplicate (platform ID): {new_job.title} at {new_job.company}")
                continue
            
            # Slow path: fuzzy matching
            is_dup = False
            for existing_job in existing_jobs:
                is_duplicate, _ = self.is_duplicate(new_job, existing_job, threshold)
                if is_duplicate:
                    is_dup = True
                    break
            
            if not is_dup:
                unique_jobs.append(new_job)
        
        logger.info(f"Filtered {len(new_jobs) - len(unique_jobs)} duplicates from {len(new_jobs)} jobs")
        return unique_jobs
    
def from_scraped_dict(job_data: dict) -> Job:
    """Build a transient, unpersisted Job for dedup comparison from a scraper result.

    Populates exactly DEDUP_IDENTITY_FIELDS — see calculate_similarity.
    """
    defaults = {"title": "", "company": "", "location": "", "platform": ""}
    return Job(**{
        field: job_data.get(field, defaults.get(field))
        for field in DEDUP_IDENTITY_FIELDS
    })


# Global instance
_deduplicator: Optional[JobDeduplicator] = None


def get_deduplicator() -> JobDeduplicator:
    """Get or create the global deduplicator instance"""
    global _deduplicator
    if _deduplicator is None:
        _deduplicator = JobDeduplicator()
    return _deduplicator
