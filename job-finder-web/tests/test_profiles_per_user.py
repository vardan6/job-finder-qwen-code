"""Regression coverage for the R9 profiles-per-user index."""
import asyncio

from starlette.requests import Request

from backend.models.candidate import Candidate
from backend.models.document import CandidateDocument
from backend.models.supporting import CandidateJobTitle
from backend.models.user import User
from backend.ownership import ensure_development_user
from backend.routes.candidates import list_candidates, profile_track_title


def _request() -> Request:
    return Request({
        "type": "http",
        "method": "GET",
        "path": "/candidates/",
        "query_string": b"",
        "headers": [],
    })


def test_profile_index_shows_only_current_users_profiles_with_primary_track(db):
    current_user = ensure_development_user(db)
    other_user = User(email="other@example.test", display_name="Other user")
    db.add(other_user)
    db.flush()

    profile = Candidate(name="Alex", current_role="Generalist", user_id=current_user.id)
    other_profile = Candidate(name="Hidden", user_id=other_user.id)
    db.add_all([profile, other_profile])
    db.flush()
    db.add_all([
        CandidateJobTitle(candidate_id=profile.id, title="Software Engineer", priority=2),
        CandidateJobTitle(candidate_id=profile.id, title="AI Engineer", priority=1),
        CandidateDocument(candidate_id=profile.id, filename="alex-resume.md", file_path="alex-resume.md"),
    ])
    db.commit()

    response = asyncio.run(list_candidates(_request(), db, current_user))
    body = response.body.decode()

    assert "My Profiles" in body
    assert "AI Engineer" in body
    assert "1 file" in body
    assert "Hidden" not in body


def test_profile_track_title_falls_back_to_current_role_and_ignores_inactive_titles(db):
    profile = Candidate(name="Alex", current_role="Data Analyst")
    db.add(profile)
    db.flush()
    db.add(CandidateJobTitle(candidate_id=profile.id, title="Old Role", priority=1, is_active=False))
    db.commit()
    db.refresh(profile)

    assert profile_track_title(profile) == "Data Analyst"
