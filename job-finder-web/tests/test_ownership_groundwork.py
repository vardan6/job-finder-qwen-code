"""Regression coverage for future Phase-12 ownership groundwork."""
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from backend.database import Base, migrate_ownership_groundwork
from backend.models.candidate import Candidate
from backend.models.user import User
from backend.ownership import (
    DEVELOPMENT_USER_EMAIL,
    ensure_development_user,
    get_current_user,
    get_owned_candidate,
)


def test_development_user_seed_is_idempotent(db):
    first = ensure_development_user(db)
    second = ensure_development_user(db)

    assert first.id == second.id
    assert second.email == DEVELOPMENT_USER_EMAIL
    assert second.account_type == "job_seeking"
    assert db.query(User).filter(User.email == DEVELOPMENT_USER_EMAIL).count() == 1


def test_current_user_returns_the_seeded_development_principal(db):
    assert get_current_user(db).email == DEVELOPMENT_USER_EMAIL


def test_get_owned_candidate_hides_candidates_of_another_user(db):
    owner = ensure_development_user(db)
    other_user = User(email="other@local", display_name="Other User")
    db.add(other_user)
    db.flush()
    owned = Candidate(name="Owned", user_id=owner.id)
    foreign = Candidate(name="Foreign", user_id=other_user.id)
    db.add_all([owned, foreign])
    db.commit()

    assert get_owned_candidate(db, owner, owned.id).id == owned.id
    with pytest.raises(HTTPException) as exc_info:
        get_owned_candidate(db, owner, foreign.id)
    assert exc_info.value.status_code == 404


def test_ownership_migration_adds_and_backfills_legacy_candidate_column():
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE candidates (id INTEGER PRIMARY KEY, name VARCHAR NOT NULL)"))
        conn.execute(text("INSERT INTO candidates (name) VALUES ('Legacy')"))

    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    migrate_ownership_groundwork(bind=engine, session_factory=Session)
    migrate_ownership_groundwork(bind=engine, session_factory=Session)

    assert "user_id" in {column["name"] for column in inspect(engine).get_columns("candidates")}
    session = Session()
    try:
        user = session.query(User).filter_by(email=DEVELOPMENT_USER_EMAIL).one()
        assert session.execute(text("SELECT user_id FROM candidates WHERE id = 1")).scalar_one() == user.id
        assert session.query(User).filter_by(email=DEVELOPMENT_USER_EMAIL).count() == 1
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()
