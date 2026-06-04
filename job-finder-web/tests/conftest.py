"""
Shared pytest fixtures for the job-finder test suite.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

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
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = Session()

    yield session

    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()
