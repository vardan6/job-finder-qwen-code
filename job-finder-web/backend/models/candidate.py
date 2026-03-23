"""
Candidate Model - Represents a job seeker
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from sqlalchemy.orm import relationship

from backend.database import Base


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String, unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    location = Column(String, default="Armenia")
    timezone = Column(String, default="Asia/Yerevan")
    experience_years = Column(Integer, nullable=True)
    current_role = Column(String, nullable=True)
    folder_path = Column(String, nullable=True)

    is_active = Column(Boolean, default=True)
    archived_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships - use string references to avoid circular dependency
    job_titles = relationship("CandidateJobTitle", back_populates="candidate", cascade="all, delete-orphan", lazy="select")
    skills = relationship("CandidateSkill", back_populates="candidate", cascade="all, delete-orphan", lazy="select")
    jobs = relationship("Job", back_populates="candidate", cascade="all, delete-orphan", lazy="select")
    preferences = relationship("CandidatePreferences", back_populates="candidate", uselist=False, cascade="all, delete-orphan", lazy="select")
    documents = relationship("CandidateDocument", back_populates="candidate", cascade="all, delete-orphan", lazy="select")
    parse_prompts = relationship("DocumentParsePrompt", back_populates="candidate", cascade="all, delete-orphan", lazy="select")

    def __repr__(self):
        return f"<Candidate(id={self.id}, name='{self.name}')>"
