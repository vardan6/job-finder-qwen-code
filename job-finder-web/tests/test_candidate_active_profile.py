"""Canonical readers for a candidate's active skills/titles and the profile seam.

These pin the single predicate every consumer shares: a skill counts only when
active AND enabled; a title counts only when active. Previously each call site
reimplemented this and one (the analysis profile) had drifted to omit the
skill `is_active` check, leaking soft-deleted skills into the prompt.
"""
from backend.models.candidate import Candidate
from backend.models.supporting import CandidateJobTitle, CandidateSkill
from backend.services.job_analysis import CandidateProfile


def _candidate(db):
    candidate = Candidate(name="Active Profile Candidate", current_role="Backend Engineer",
                          location="Armenia", timezone="Asia/Yerevan", experience_years=8,
                          folder_path="/tmp/active-profile")
    db.add(candidate)
    db.flush()
    db.add_all((
        CandidateSkill(candidate_id=candidate.id, skill_name="Python", is_active=True, is_enabled=True),
        CandidateSkill(candidate_id=candidate.id, skill_name="Disabled", is_active=True, is_enabled=False),
        CandidateSkill(candidate_id=candidate.id, skill_name="Deleted", is_active=False, is_enabled=True),
        CandidateSkill(candidate_id=candidate.id, skill_name="  ", is_active=True, is_enabled=True),
        CandidateJobTitle(candidate_id=candidate.id, title="Staff Engineer", priority=1, is_active=True),
        CandidateJobTitle(candidate_id=candidate.id, title="Backend Engineer", priority=3, is_active=True),
        CandidateJobTitle(candidate_id=candidate.id, title="Retired Title", priority=2, is_active=False),
    ))
    db.commit()
    return candidate


def test_active_skill_names_excludes_disabled_deleted_and_blank(db):
    candidate = _candidate(db)
    assert candidate.active_skill_names() == ["Python"]


def test_active_titles_are_priority_ordered_and_exclude_inactive(db):
    candidate = _candidate(db)
    assert candidate.active_titles() == ["Staff Engineer", "Backend Engineer"]


def test_profile_from_candidate_does_not_leak_soft_deleted_skills(db):
    candidate = _candidate(db)
    profile = CandidateProfile.from_candidate(candidate)

    assert profile.skills == ["Python"]
    assert "Deleted" not in profile.skills
    assert profile.target_roles == ["Staff Engineer", "Backend Engineer"]
    assert profile.location == "Armenia"
    assert profile.timezone == "Asia/Yerevan"
    assert profile.experience_years == 8
    assert profile.current_role == "Backend Engineer"
