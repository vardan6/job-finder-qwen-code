"""
Job Model - Represents a job posting
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, func
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

    # Description storage (file-based)
    description_hash = Column(String, nullable=True)  # For deduplication
    description_snippet = Column(Text, nullable=True)  # First 500 chars
    description_path = Column(String, nullable=True)  # Path to full description file

    # Scores
    ai_remote_score = Column(Integer, nullable=True)
    custom_fit_score = Column(Integer, nullable=True)

    # Status
    status = Column(String, default="active")  # active, expired, applied, etc.
    is_new = Column(Boolean, default=True)
    posted_date = Column(DateTime, nullable=True)
    found_at = Column(DateTime, server_default=func.now())

    # Relationships
    candidate = relationship("Candidate", back_populates="jobs")
    application = relationship("JobApplication", back_populates="job", uselist=False, cascade="all, delete-orphan")

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
