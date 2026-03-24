"""
Supporting Models - Job Titles, Skills, Preferences
"""
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text
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
    source_document_id = Column(Integer, ForeignKey("candidate_documents.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True)

    candidate = relationship("Candidate", back_populates="job_titles")
    source_document = relationship("CandidateDocument", backref="job_titles")


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
    source_document_id = Column(Integer, ForeignKey("candidate_documents.id", ondelete="SET NULL"), nullable=True)

    candidate = relationship("Candidate", back_populates="skills")
    source_document = relationship("CandidateDocument", backref="skills")


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
