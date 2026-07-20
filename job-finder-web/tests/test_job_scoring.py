"""Regression fixtures for R5 deterministic composite scoring."""
import json

from backend.models.candidate import Candidate
from backend.models.supporting import CandidateJobTitle, CandidateSkill
from backend.services.job_scoring import score_job, skills_overlap_score, title_match_score
from backend.services.job_search import JobSearchService


def test_title_match_ordering_fixture_handles_aliases_and_empty_descriptions():
    """Representative title ordering must not depend on description presence."""
    preferred_titles = ["Software Engineer", "Data Scientist"]
    jobs = [
        ("alias", "Senior SWE", ""),
        ("exact", "Software Engineer", None),
        ("related", "Data Analyst", "A detailed but unrelated description."),
        ("unrelated", "Sales Manager", ""),
    ]

    ordered_ids = [
        identifier
        for identifier, _, _ in sorted(
            jobs,
            key=lambda job: title_match_score(job[1], preferred_titles),
            reverse=True,
        )
    ]

    assert ordered_ids == ["alias", "exact", "related", "unrelated"]


def test_saved_job_persists_title_score_without_a_description(db):
    candidate = Candidate(name="Scoring Candidate", folder_path="/tmp/scoring-candidate")
    db.add(candidate)
    db.flush()
    db.add(CandidateJobTitle(candidate_id=candidate.id, title="Software Engineer", is_active=True))
    db.commit()

    job = JobSearchService(db)._create_job_record(
        {"title": "SWE", "company": "Acme", "platform": "linkedin", "description": ""},
        candidate.id,
    )
    db.add(job)
    db.commit()

    assert job.deterministic_score == 100
    assert job.scoring_version
    assert json.loads(job.score_breakdown) == {
        "composite_score": 100,
        "skills_overlap": None,
        "skills_status": "no_description",
        "title_similarity": 100,
    }


def test_skills_overlap_matches_aliases_as_whole_phrases():
    assert skills_overlap_score(
        "We use AWS, ReactJS, and PostgreSQL. Javascripting is unrelated.",
        ["Amazon Web Services", "React", "PostgreSQL", "Java"],
    ) == 0.75


def test_composite_uses_weighted_skills_and_title_breakdown():
    score = score_job(
        "Backend Engineer",
        "Build APIs with Python and AWS.",
        ["Backend Engineer"],
        ["Python", "Amazon Web Services", "React"],
    )

    assert score.title_similarity == 100
    assert score.skills_overlap == 2 / 3
    assert score.composite_score == 87
    assert score.skills_status == "matched"
    assert score.scoring_version.startswith("r5-composite-v1:")


def test_saved_job_persists_weighted_score_and_breakdown(db):
    candidate = Candidate(name="Composite Candidate", folder_path="/tmp/composite-candidate")
    db.add(candidate)
    db.flush()
    db.add_all([
        CandidateJobTitle(candidate_id=candidate.id, title="Backend Engineer", is_active=True),
        CandidateSkill(candidate_id=candidate.id, skill_name="Python", is_active=True, is_enabled=True),
        CandidateSkill(candidate_id=candidate.id, skill_name="Amazon Web Services", is_active=True, is_enabled=True),
    ])
    db.commit()

    job = JobSearchService(db)._create_job_record(
        {"title": "Backend Engineer", "company": "Acme", "description": "Python on AWS"},
        candidate.id,
    )
    db.add(job)
    db.commit()

    assert job.deterministic_score == 100
    assert json.loads(job.score_breakdown)["skills_overlap"] == 1.0
