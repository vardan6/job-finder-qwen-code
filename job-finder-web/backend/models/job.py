"""
Job Model - Represents a job posting
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship

from backend.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)

    # Job information
    title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    location = Column(String, nullable=True)
    platform = Column(String, nullable=True)  # linkedin, glassdoor, etc.
    platform_job_id = Column(String, nullable=True)  # Platform's internal job ID
    original_url = Column(Text, nullable=True)
    salary = Column(String, nullable=True)  # Source-provided display range; not normalized compensation data.

    # Description storage (file-based)
    description_hash = Column(String, nullable=True)  # For deduplication
    description_snippet = Column(Text, nullable=True)  # First 500 chars
    description_path = Column(String, nullable=True)  # Path to full description file

    # Scores
    deterministic_score = Column(Integer, nullable=True)  # R5 profile title/composite score (0-100)
    score_breakdown = Column(Text, nullable=True)  # JSON: deterministic score dimensions/status
    scoring_version = Column(String, nullable=True)  # Algorithm + scoring-config fingerprint
    # Optional R5 refinement.  These never participate in the default sort.
    llm_score = Column(Integer, nullable=True)
    llm_rationale = Column(Text, nullable=True)
    llm_prompt_version = Column(String, nullable=True)
    llm_profile_fingerprint = Column(String, nullable=True)
    # R6 remote verification.  The enum is stored as text for SQLite
    # portability; callers must use the documented lower-case values.
    verified_remote_status = Column(String, nullable=True)
    remote_restrictions = Column(Text, nullable=True)  # JSON normalized restrictions
    remote_evidence = Column(Text, nullable=True)  # JSON verbatim contradiction evidence
    remote_verified_version = Column(String, nullable=True)
    ai_remote_score = Column(Integer, nullable=True)
    custom_fit_score = Column(Integer, nullable=True)

    # Status
    status = Column(String, default="active")  # active, expired, applied, etc.
    # Curation is deliberately separate from application status: a dismissed
    # posting remains in historical search snapshots, but is hidden by default.
    is_dismissed = Column(Boolean, nullable=False, default=False, server_default="0")
    is_new = Column(Boolean, default=True)
    posted_date = Column(DateTime, nullable=True)
    found_at = Column(DateTime, server_default=func.now())

    # Relationships
    candidate = relationship("Candidate", back_populates="jobs")
    application = relationship("JobApplication", back_populates="job", uselist=False, cascade="all, delete-orphan")
    search_run_memberships = relationship("SearchRunJob", back_populates="job", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Job(id={self.id}, title='{self.title}', company='{self.company}')>"


class JobApplication(Base):
    """Application tracking for a job"""
    __tablename__ = "job_applications"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, unique=True)

    status = Column(String, default="interested")  # interested, applied, interview, offer, rejected
    applied_date = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    follow_up_date = Column(DateTime, nullable=True)

    job = relationship("Job", back_populates="application")


class SearchRun(Base):
    """A named, historical set of search results for one candidate."""
    __tablename__ = "search_runs"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    query = Column(Text, nullable=False)
    location = Column(String, nullable=True)
    platforms = Column(Text, nullable=False)  # JSON platform set used for this run
    started_at = Column(DateTime, nullable=False, server_default=func.now())
    finished_at = Column(DateTime, nullable=True)

    candidate = relationship("Candidate", back_populates="search_runs")
    jobs = relationship("SearchRunJob", back_populates="search_run", cascade="all, delete-orphan")


class SearchRunJob(Base):
    """One job's immutable display snapshot within a search run."""
    __tablename__ = "search_run_jobs"
    __table_args__ = (
        UniqueConstraint("search_run_id", "job_id", name="uq_search_run_job"),
    )

    id = Column(Integer, primary_key=True, index=True)
    search_run_id = Column(Integer, ForeignKey("search_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    first_sighting = Column(Boolean, nullable=False, default=False)
    sighted_platforms = Column(Text, nullable=False)  # JSON list for this run

    deterministic_score = Column(Integer, nullable=True)
    scoring_version = Column(String, nullable=True)
    llm_score = Column(Integer, nullable=True)
    llm_prompt_version = Column(String, nullable=True)
    verified_remote_status = Column(String, nullable=True)
    remote_verified_version = Column(String, nullable=True)
    salary = Column(String, nullable=True)

    search_run = relationship("SearchRun", back_populates="jobs")
    job = relationship("Job", back_populates="search_run_memberships")
