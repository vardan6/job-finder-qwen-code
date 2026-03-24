"""
Platform Account Model - For storing LinkedIn/Glassdoor credentials
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, func, ForeignKey
from sqlalchemy.orm import relationship

from backend.database import Base


class PlatformAccount(Base):
    """Platform account credentials for a candidate"""
    __tablename__ = "platform_accounts"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    platform = Column(String, nullable=False)  # linkedin, glassdoor, indeed
    email_encrypted = Column(Text, nullable=True)  # Encrypted email (optional)
    cookies_encrypted = Column(Text, nullable=True)  # Encrypted session cookies
    status = Column(String, default="inactive")  # inactive, active, expired, captcha_required
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    candidate = relationship("Candidate", back_populates="platform_accounts")

    __table_args__ = (
        # Unique constraint: one account per platform per candidate
        {'sqlite_autoincrement': True}
    )


# Add backref to Candidate model
# This is done in candidate.py
