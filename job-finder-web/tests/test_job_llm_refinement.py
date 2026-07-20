"""R5 optional top-N LLM refinement stays bounded and companion-only."""
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine, inspect, text

from backend.database import migrate_llm_job_refinement
from backend.models.candidate import Candidate
from backend.models.job import Job
from backend.models.supporting import CandidateJobTitle, CandidateSkill
from backend.services.job_llm_refinement import JobLLMRefinementService, profile_fingerprint


def _candidate(db):
    candidate = Candidate(name="Refinement Candidate", current_role="Backend Engineer", folder_path="/tmp/refinement")
    db.add(candidate)
    db.flush()
    db.add_all((
        CandidateJobTitle(candidate_id=candidate.id, title="Backend Engineer", is_active=True),
        CandidateSkill(candidate_id=candidate.id, skill_name="Python", is_active=True, is_enabled=True),
    ))
    db.commit()
    return candidate


def _job(candidate_id, score, title):
    return Job(candidate_id=candidate_id, title=title, company="Acme", deterministic_score=score, description_snippet="Python APIs")


@pytest.mark.asyncio
async def test_refines_only_deterministic_top_n_and_keeps_composite_unchanged(db):
    candidate = _candidate(db)
    jobs = [_job(candidate.id, score, f"Job {score}") for score in (90, 80, 70)]
    db.add_all(jobs)
    db.commit()
    service = JobLLMRefinementService(db)

    with patch("backend.services.job_llm_refinement.send_message", new_callable=AsyncMock,
               return_value='{"llm_score": 11, "rationale": "A concise fit rationale."}') as send:
        count = await service.refine_top_jobs(candidate, top_n=2)

    assert count == 2
    assert send.call_count == 2
    assert [job.deterministic_score for job in service.top_deterministic_jobs(candidate.id, 3)] == [90, 80, 70]
    assert [job.llm_score for job in service.top_deterministic_jobs(candidate.id, 3)] == [11, 11, None]
    _, kwargs = send.call_args
    assert kwargs["routing_purpose"] == "candidate_analysis"


@pytest.mark.asyncio
async def test_same_job_profile_and_prompt_is_idempotent(db):
    candidate = _candidate(db)
    db.add(_job(candidate.id, 90, "Backend Engineer"))
    db.commit()
    service = JobLLMRefinementService(db)

    with patch("backend.services.job_llm_refinement.send_message", new_callable=AsyncMock,
               return_value='{"llm_score": 87, "rationale": "Strong Python alignment."}') as send:
        assert await service.refine_top_jobs(candidate) == 1
        assert await service.refine_top_jobs(candidate) == 0

    send.assert_called_once()


@pytest.mark.asyncio
async def test_profile_or_prompt_change_invalidates_refinement_idempotency(db):
    candidate = _candidate(db)
    db.add(_job(candidate.id, 90, "Backend Engineer"))
    db.commit()
    service = JobLLMRefinementService(db)
    response = '{"llm_score": 87, "rationale": "Strong Python alignment."}'

    with patch("backend.services.job_llm_refinement.send_message", new_callable=AsyncMock, return_value=response) as send:
        assert await service.refine_top_jobs(candidate) == 1
        db.add(CandidateSkill(candidate_id=candidate.id, skill_name="AWS", is_active=True, is_enabled=True))
        db.commit()
        assert await service.refine_top_jobs(candidate) == 1
        assert await JobLLMRefinementService(db, prompt_version="r5-llm-refinement-v2").refine_top_jobs(candidate) == 1

    assert send.call_count == 3


def test_profile_fingerprint_ignores_skill_order_and_uses_candidate_profile(db):
    candidate = _candidate(db)
    first = profile_fingerprint(candidate)
    db.add(CandidateSkill(candidate_id=candidate.id, skill_name="Docker", is_active=True, is_enabled=True))
    db.commit()
    assert profile_fingerprint(candidate) != first


def test_migration_adds_refinement_columns_to_existing_jobs_table():
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE jobs (id INTEGER PRIMARY KEY)"))

    migrate_llm_job_refinement(bind=engine)

    columns = {column["name"] for column in inspect(engine).get_columns("jobs")}
    assert {"llm_score", "llm_rationale", "llm_prompt_version", "llm_profile_fingerprint"} <= columns
