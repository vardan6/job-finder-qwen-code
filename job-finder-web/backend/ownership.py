"""Temporary development principal and candidate ownership helpers."""
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.candidate import Candidate
from backend.models.user import User

DEVELOPMENT_USER_EMAIL = "dev@local"
DEVELOPMENT_USER_DISPLAY_NAME = "Development User"


def ensure_development_user(db: Session) -> User:
    """Return the fixed Phase-9 principal, creating it once if needed."""
    user = db.query(User).filter(User.email == DEVELOPMENT_USER_EMAIL).first()
    if user is None:
        user = User(
            email=DEVELOPMENT_USER_EMAIL,
            display_name=DEVELOPMENT_USER_DISPLAY_NAME,
            account_type="job_seeking",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def get_current_user(db: Session = Depends(get_db)) -> User:
    """Auto-login dependency until Phase 10 session authentication lands."""
    return ensure_development_user(db)


def get_owned_candidate(db: Session, user: User, candidate_id: int) -> Candidate:
    """Load a candidate only when it belongs to the supplied principal."""
    candidate = (
        db.query(Candidate)
        .filter(Candidate.id == candidate_id, Candidate.user_id == user.id)
        .first()
    )
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate
