"""Regression coverage for R10 profile visibility."""
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from backend.database import migrate_profile_visibility
from backend.models.candidate import Candidate


def test_candidate_visibility_defaults_to_draft(db):
    candidate = Candidate(name="Draft profile")
    db.add(candidate)
    db.commit()

    assert candidate.visibility_status == "draft"


def test_candidate_visibility_is_limited_to_product_statuses(db):
    db.add(Candidate(name="Invalid visibility", visibility_status="shared"))

    with pytest.raises(IntegrityError):
        db.commit()


def test_visibility_migration_backfills_legacy_candidates_to_draft():
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE candidates (id INTEGER PRIMARY KEY, name VARCHAR NOT NULL)"))
        conn.execute(text("INSERT INTO candidates (name) VALUES ('Legacy profile')"))

    migrate_profile_visibility(bind=engine)
    migrate_profile_visibility(bind=engine)

    assert "visibility_status" in {
        column["name"] for column in inspect(engine).get_columns("candidates")
    }
    with engine.connect() as conn:
        assert conn.execute(
            text("SELECT visibility_status FROM candidates WHERE id = 1")
        ).scalar_one() == "draft"
    engine.dispose()
