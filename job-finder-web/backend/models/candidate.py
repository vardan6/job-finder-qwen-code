"""
Candidate Model - Represents a job seeker
"""
import uuid

from sqlalchemy import CheckConstraint, Column, ForeignKey, Integer, String, Boolean, DateTime, func, select
from sqlalchemy.orm import relationship

from backend.database import Base
from backend.models.user import User


_development_user_id = (
    select(User.id)
    .where(User.email == "dev@local")
    .scalar_subquery()
)


class Candidate(Base):
    __tablename__ = "candidates"
    __table_args__ = (
        CheckConstraint(
            "visibility_status IN ('draft', 'private', 'public')",
            name="ck_candidate_visibility_status",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
        default=_development_user_id,
    )
    uuid = Column(String, unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    location = Column(String, default="Armenia")
    timezone = Column(String, default="Asia/Yerevan")
    experience_years = Column(Integer, nullable=True)
    current_role = Column(String, nullable=True)
    folder_path = Column(String, nullable=True)
    # `public` is reserved for future job-provider discovery (R10).
    visibility_status = Column(String, nullable=False, default="draft", server_default="draft")

    is_active = Column(Boolean, default=True)
    archived_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships - use string references to avoid circular dependency
    job_titles = relationship("CandidateJobTitle", back_populates="candidate", cascade="all, delete-orphan", lazy="select")
    skills = relationship("CandidateSkill", back_populates="candidate", cascade="all, delete-orphan", lazy="select")
    jobs = relationship("Job", back_populates="candidate", cascade="all, delete-orphan", lazy="select")
    search_runs = relationship("SearchRun", back_populates="candidate", cascade="all, delete-orphan", lazy="select")
    preferences = relationship("CandidatePreferences", back_populates="candidate", uselist=False, cascade="all, delete-orphan", lazy="select")
    documents = relationship("CandidateDocument", back_populates="candidate", cascade="all, delete-orphan", lazy="select")
    platform_accounts = relationship("PlatformAccount", back_populates="candidate", cascade="all, delete-orphan", lazy="select")
    parse_prompts = relationship("DocumentParsePrompt", back_populates="candidate", cascade="all, delete-orphan", lazy="select")
    user = relationship("User", back_populates="candidates")

    def __repr__(self):
        return f"<Candidate(id={self.id}, name='{self.name}')>"
