"""User model for ownership boundaries.

Phase 9 uses a single seeded development user.  Real authentication replaces
that principal source in Phase 10 without changing ownership call sites.
"""
from sqlalchemy import Column, DateTime, Integer, String, func
from sqlalchemy.orm import relationship

from backend.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False, unique=True, index=True)
    display_name = Column(String, nullable=False)
    account_type = Column(String, nullable=False, default="job_seeking")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    candidates = relationship("Candidate", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}')>"
