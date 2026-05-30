"""
Shared pytest fixtures for the job-finder test suite.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import Base to create all tables in the in-memory DB
from backend.database import Base


@pytest.fixture
def db():
    """
    In-memory SQLite session for each test.

    Creates a fresh database with all tables, yields the session, then tears
    everything down.  Tests that hit the database should request this fixture.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = Session()

    yield session

    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()
