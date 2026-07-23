"""Deterministic R6 remote-verification contract tests (provider mocked)."""
import json
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine, inspect, text

from backend.database import Base, migrate_remote_verification
from backend.models.job import Job
from backend.services.job_analysis import (
    CandidateProfile, JobAnalysisService, REMOTE_VERIFICATION_PROMPT_VERSION,
)


def response(status, restrictions=None, evidence=None):
    return json.dumps({
        "remote_score": 99, "remote_type": "Fully Remote", "location_requirement": "Worldwide",
        "citizenship_required": None, "office_visits": "Never", "timezone_requirement": None,
        "matched_skills": [], "missing_skills": [], "skill_match_score": 0,
        "experience_level": "Senior", "red_flags": [], "summary": "", "recommendation": "Consider",
        "verified_remote_status": status, "remote_restrictions": restrictions, "remote_evidence": evidence,
    })


@pytest.mark.asyncio
@pytest.mark.parametrize(("description", "payload", "expected_status", "restriction_key", "expected_value"), [
    ("This remote role is open to US-only applicants.", response("remote_restricted", {"regions": ["United States"]}, ["US-only applicants"]), "remote_restricted", "regions", ["US"]),
    ("Remote work requires four hours of PST timezone overlap.", response("remote_restricted", {"timezone_overlap": "four hours of PST"}, ["requires four hours of PST timezone overlap"]), "remote_restricted", "timezone_overlap", "four hours of PST"),
    ("Fully remote, but quarterly on-site weeks are required.", response("remote_restricted", {"office_visits": "occasional"}, ["quarterly on-site weeks"]), "remote_restricted", "office_visits", "occasional"),
    ("We are flexible/hybrid-friendly depending on team needs.", response("hybrid", evidence=["flexible/hybrid-friendly"]), "hybrid", None, None),
])
async def test_remote_contradiction_fixtures(description, payload, expected_status, restriction_key, expected_value):
    service = JobAnalysisService()
    with patch("backend.services.job_analysis.send_message", new_callable=AsyncMock, return_value=payload):
        result = await service.analyze_job(description, CandidateProfile(skills=[]), use_cache=False, platform_remote_attribute="remote")
    assert result.verified_remote_status == expected_status
    assert result.remote_verified_version == REMOTE_VERIFICATION_PROMPT_VERSION
    if restriction_key:
        assert result.remote_restrictions[restriction_key] == expected_value
        assert result.remote_evidence


@pytest.mark.asyncio
async def test_empty_description_is_unknown_without_provider_call():
    service = JobAnalysisService()
    with patch("backend.services.job_analysis.send_message", new_callable=AsyncMock) as provider:
        result = await service.analyze_job("", CandidateProfile(skills=[]), use_cache=False)
    provider.assert_not_called()
    assert result.verified_remote_status == "unknown"
    assert result.remote_evidence is None


@pytest.mark.asyncio
async def test_contradiction_without_verbatim_quote_falls_back_to_unknown():
    service = JobAnalysisService()
    with patch("backend.services.job_analysis.send_message", new_callable=AsyncMock,
               return_value=response("remote_restricted", {"regions": ["US"]}, ["paraphrased restriction"])):
        result = await service.analyze_job("Remote work limited to US applicants.", CandidateProfile(skills=[]), use_cache=False, platform_remote_attribute="remote")
    assert result.verified_remote_status == "unknown"
    assert result.remote_restrictions is None


def test_remote_verification_migration_is_idempotent():
    engine = create_engine("sqlite://")
    # Simulate a pre-R6 jobs table while retaining enough columns for migration.
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE jobs (id INTEGER PRIMARY KEY)"))
    migrate_remote_verification(engine)
    migrate_remote_verification(engine)
    columns = {column["name"] for column in inspect(engine).get_columns("jobs")}
    assert {"verified_remote_status", "remote_restrictions", "remote_evidence", "remote_verified_version"} <= columns


def test_job_model_exposes_persisted_remote_contract():
    columns = set(Job.__table__.columns.keys())
    assert {"verified_remote_status", "remote_restrictions", "remote_evidence", "remote_verified_version"} <= columns
