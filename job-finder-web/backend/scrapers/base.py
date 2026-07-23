"""Small provider-neutral contract for job-platform adapters."""
from dataclasses import dataclass
from typing import Callable, Optional, Protocol, Sequence, runtime_checkable


@dataclass(frozen=True)
class PlatformJob:
    """Normalized, source-preserving job result emitted by a platform."""

    title: str
    company: str
    location: str
    posted_date: Optional[str]
    job_url: str
    platform_job_id: Optional[str]
    description: Optional[str] = None
    description_hash: Optional[str] = None
    snippet: Optional[str] = None
    apply_url: Optional[str] = None
    remote_eligibility: Optional[str] = None
    source_timestamp: Optional[str] = None
    salary: Optional[str] = None
    job_type: Optional[str] = None

    def to_dict(self) -> dict:
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
            "apply_url": self.apply_url,
            "remote_eligibility": self.remote_eligibility,
            "source_timestamp": self.source_timestamp,
            "salary": self.salary,
            "job_type": self.job_type,
        }


@runtime_checkable
class JobPlatformAdapter(Protocol):
    """Minimal common surface for a stateful job-platform integration."""

    async def search_jobs(
        self,
        query: str,
        location: str = "",
        max_jobs: int = 20,
        cookies_path: Optional[str] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> Sequence[PlatformJob]:
        ...


class ScraperSessionState:
    """Session-outcome attributes every adapter reports back after search_jobs.

    Consumed by JobSearchService to update PlatformAccount status and surface
    skip/error reasons uniformly across platforms — see
    JobSearchService._apply_scraper_outcome. Adapters set these in place of
    raising, since a failed/blocked search still returns a (possibly empty)
    result rather than an exception.
    """

    def __init__(self):
        self.manual_challenge_handoff = False
        self.login_wall_detected = False
        self.rate_limited_reason: Optional[str] = None
        self.last_error: Optional[str] = None
