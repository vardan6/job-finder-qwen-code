"""
Supporting Models - Job Titles, Skills, Preferences
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import relationship

from backend.database import Base


class CandidateJobTitle(Base):
    """Preferred job titles for a candidate"""
    __tablename__ = "candidate_job_titles"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    priority = Column(Integer, default=2)  # 1=High, 2=Medium, 3=Low
    description = Column(Text, nullable=True)  # Optional description/note
    source = Column(String, nullable=False, default="edited")
    original_extracted_value = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)

    candidate = relationship("Candidate", back_populates="job_titles")
    extraction_occurrences = relationship(
        "ExtractionOccurrence", back_populates="job_title", cascade="all, delete-orphan"
    )


class CandidateSkill(Base):
    """Skills for a candidate"""
    __tablename__ = "candidate_skills"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    skill_name = Column(String, nullable=False)
    category = Column(String, default="preferred")  # required, preferred
    years_experience = Column(Integer, nullable=True)
    is_enabled = Column(Boolean, default=True)  # Toggle for search matching
    is_active = Column(Boolean, default=True)  # Soft delete flag
    source = Column(String, nullable=False, default="edited")
    original_extracted_value = Column(String, nullable=True)

    candidate = relationship("Candidate", back_populates="skills")
    extraction_occurrences = relationship(
        "ExtractionOccurrence", back_populates="skill", cascade="all, delete-orphan"
    )


class ExtractionOccurrence(Base):
    """An immutable per-file fact that produced a curated profile value."""
    __tablename__ = "extraction_occurrences"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("candidate_documents.id", ondelete="CASCADE"), nullable=False)
    job_title_id = Column(Integer, ForeignKey("candidate_job_titles.id", ondelete="CASCADE"), nullable=True)
    skill_id = Column(Integer, ForeignKey("candidate_skills.id", ondelete="CASCADE"), nullable=True)
    raw_extracted_value = Column(String, nullable=False)
    extractor_version = Column(String, nullable=True)
    extracted_at = Column(DateTime, nullable=False, server_default=func.now())

    document = relationship("CandidateDocument", backref="extraction_occurrences")
    job_title = relationship("CandidateJobTitle", back_populates="extraction_occurrences")
    skill = relationship("CandidateSkill", back_populates="extraction_occurrences")


class CandidatePreferences(Base):
    """Search and filter preferences for a candidate"""
    __tablename__ = "candidate_preferences"
    
    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    min_score = Column(Integer, default=60)
    min_ai_remote_score = Column(Integer, default=70)
    remote_only = Column(Boolean, default=False)
    experience_levels = Column(Text, default='["Senior", "Staff", "Principal", "Lead"]')  # JSON
    
    candidate = relationship("Candidate", back_populates="preferences")
