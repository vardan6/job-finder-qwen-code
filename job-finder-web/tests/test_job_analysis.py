"""
Tests for job_analysis.py

Mocks LLM calls so no real model is required.
Tests focus on caching logic, Armenia compatibility, and response parsing.
"""
import json
import pytest
from unittest.mock import AsyncMock, patch

from backend.services.job_analysis import JobAnalysis, JobAnalysisService, JOB_ANALYSIS_PROMPT


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_analysis(**kwargs) -> JobAnalysis:
    """Build a JobAnalysis with sensible defaults, overriding with kwargs."""
    defaults = dict(
        remote_score=90,
        remote_type="Fully Remote",
        location_requirement="Worldwide",
        citizenship_required=None,
        office_visits="Never",
        timezone_requirement=None,
        matched_skills=["Python", "FastAPI"],
        missing_skills=[],
        skill_match_score=85,
        experience_level="Mid",
        red_flags=[],
        summary="Great remote role.",
        recommendation="Apply",
    )
    defaults.update(kwargs)
    return JobAnalysis(**defaults)


VALID_LLM_RESPONSE = json.dumps({
    "remote_score": 92,
    "remote_type": "Fully Remote",
    "location_requirement": "Worldwide",
    "citizenship_required": None,
    "office_visits": "Never",
    "timezone_requirement": "Flexible",
    "matched_skills": ["Python", "Docker"],
    "missing_skills": ["Kubernetes"],
    "skill_match_score": 80,
    "experience_level": "Senior",
    "red_flags": [],
    "summary": "Excellent remote-first opportunity.",
    "recommendation": "Apply",
})


# ---------------------------------------------------------------------------
# Cache key
# ---------------------------------------------------------------------------

class TestCacheKey:
    def test_same_description_and_skills_same_key(self):
        svc = JobAnalysisService()
        k1 = svc._get_cache_key("job desc", ["Python", "Docker"])
        k2 = svc._get_cache_key("job desc", ["Python", "Docker"])
        assert k1 == k2

    def test_different_description_different_key(self):
        svc = JobAnalysisService()
        k1 = svc._get_cache_key("job desc A", ["Python"])
        k2 = svc._get_cache_key("job desc B", ["Python"])
        assert k1 != k2

    def test_different_skills_different_key(self):
        svc = JobAnalysisService()
        k1 = svc._get_cache_key("same description", ["Python"])
        k2 = svc._get_cache_key("same description", ["Go"])
        assert k1 != k2

    def test_skills_order_does_not_affect_key(self):
        """Skills are sorted before hashing, so order shouldn't matter."""
        svc = JobAnalysisService()
        k1 = svc._get_cache_key("desc", ["Python", "Docker", "FastAPI"])
        k2 = svc._get_cache_key("desc", ["FastAPI", "Python", "Docker"])
        assert k1 == k2

    def test_different_candidate_profile_different_key(self):
        """Two candidates with identical description/skills must not share a cache entry."""
        svc = JobAnalysisService()
        k1 = svc._get_cache_key("desc", ["Python"], candidate_profile_key="Armenia|Asia/Yerevan")
        k2 = svc._get_cache_key("desc", ["Python"], candidate_profile_key="Canada|America/Toronto")
        assert k1 != k2

    def test_no_candidate_profile_matches_legacy_key(self):
        """Callers that omit candidate profile fields keep the pre-existing key shape."""
        svc = JobAnalysisService()
        assert svc._get_cache_key("desc", ["Python"]) == svc._get_cache_key("desc", ["Python"], "")


# ---------------------------------------------------------------------------
# Cache hit/miss
# ---------------------------------------------------------------------------

class TestCaching:
    @pytest.mark.asyncio
    async def test_cache_hit_does_not_call_llm(self, tmp_path):
        """If a cached result exists, the LLM must not be called."""
        svc = JobAnalysisService()
        svc._cache_dir = tmp_path  # redirect cache to temp dir

        # Pre-populate cache
        analysis = make_analysis()
        key = svc._get_cache_key("my job description", ["Python"])
        cache_path = tmp_path / f"{key}.json"
        cache_path.write_text(json.dumps(analysis.to_dict()))

        with patch("backend.services.job_analysis.send_message", new_callable=AsyncMock) as mock_llm:
            result = await svc.analyze_job("my job description", ["Python"], use_cache=True)
            mock_llm.assert_not_called()

        assert result.remote_score == 90

    @pytest.mark.asyncio
    async def test_cache_miss_calls_llm(self, tmp_path):
        """Without a cached result the LLM is called exactly once."""
        svc = JobAnalysisService()
        svc._cache_dir = tmp_path

        with patch(
            "backend.services.job_analysis.send_message",
            new_callable=AsyncMock,
            return_value=VALID_LLM_RESPONSE,
        ) as mock_llm:
            result = await svc.analyze_job("fresh description", ["Go"], use_cache=True)
            mock_llm.assert_called_once()

        assert result.remote_score == 92

    @pytest.mark.asyncio
    async def test_result_is_written_to_cache(self, tmp_path):
        """After a successful LLM call the result should be cached on disk."""
        svc = JobAnalysisService()
        svc._cache_dir = tmp_path

        with patch(
            "backend.services.job_analysis.send_message",
            new_callable=AsyncMock,
            return_value=VALID_LLM_RESPONSE,
        ):
            await svc.analyze_job("job desc", ["Python"], use_cache=True)

        key = svc._get_cache_key("job desc", ["Python"])
        cache_path = tmp_path / f"{key}.json"
        assert cache_path.exists()

    @pytest.mark.asyncio
    async def test_use_cache_false_always_calls_llm(self, tmp_path):
        """use_cache=False should bypass cache even if a file exists."""
        svc = JobAnalysisService()
        svc._cache_dir = tmp_path

        # Pre-populate cache
        analysis = make_analysis()
        key = svc._get_cache_key("desc", ["Python"])
        cache_path = tmp_path / f"{key}.json"
        cache_path.write_text(json.dumps(analysis.to_dict()))

        with patch(
            "backend.services.job_analysis.send_message",
            new_callable=AsyncMock,
            return_value=VALID_LLM_RESPONSE,
        ) as mock_llm:
            await svc.analyze_job("desc", ["Python"], use_cache=False)
            mock_llm.assert_called_once()

    @pytest.mark.asyncio
    async def test_calls_send_message_with_candidate_analysis_routing(self, tmp_path):
        svc = JobAnalysisService()
        svc._cache_dir = tmp_path

        fake_db = object()
        with patch(
            "backend.services.job_analysis.send_message",
            new_callable=AsyncMock,
            return_value=VALID_LLM_RESPONSE,
        ) as mock_llm:
            await svc.analyze_job("desc", ["Python"], use_cache=False, db=fake_db)

        _, kwargs = mock_llm.call_args
        assert kwargs["db"] is fake_db
        assert kwargs["routing_purpose"] == "candidate_analysis"


# ---------------------------------------------------------------------------
# Candidate-specific prompt
# ---------------------------------------------------------------------------

class TestCandidateProfilePrompt:
    def test_prompt_template_has_no_hardcoded_candidate(self):
        """The template must not bake in any one candidate's profile."""
        for needle in ("Armenia", "EDA", "VLSI", "18+ years"):
            assert needle not in JOB_ANALYSIS_PROMPT

    @pytest.mark.asyncio
    async def test_prompt_uses_given_candidate_profile(self, tmp_path):
        svc = JobAnalysisService()
        svc._cache_dir = tmp_path

        with patch(
            "backend.services.job_analysis.send_message",
            new_callable=AsyncMock,
            return_value=VALID_LLM_RESPONSE,
        ) as mock_llm:
            await svc.analyze_job(
                "desc", ["Python"], use_cache=False,
                candidate_location="Canada",
                candidate_timezone="America/Toronto",
                candidate_experience_years=5,
                candidate_current_role="Backend Engineer",
                candidate_target_roles=["Staff Engineer", "Tech Lead"],
            )

        prompt = mock_llm.call_args[0][0]
        assert "Canada" in prompt
        assert "America/Toronto" in prompt
        assert "5+ years, currently Backend Engineer" in prompt
        assert "Staff Engineer, Tech Lead" in prompt

    @pytest.mark.asyncio
    async def test_prompt_falls_back_when_profile_omitted(self, tmp_path):
        svc = JobAnalysisService()
        svc._cache_dir = tmp_path

        with patch(
            "backend.services.job_analysis.send_message",
            new_callable=AsyncMock,
            return_value=VALID_LLM_RESPONSE,
        ) as mock_llm:
            await svc.analyze_job("desc", ["Python"], use_cache=False)

        prompt = mock_llm.call_args[0][0]
        assert "Not specified" in prompt


# ---------------------------------------------------------------------------
# Armenia compatibility
# ---------------------------------------------------------------------------

class TestArmeniaCompatibility:
    def test_fully_remote_worldwide_is_compatible(self):
        svc = JobAnalysisService()
        analysis = make_analysis(
            remote_type="Fully Remote",
            location_requirement="Worldwide",
            citizenship_required=None,
            office_visits="Never",
            timezone_requirement=None,
        )
        is_ok, issues = svc.calculate_armenia_compatibility(analysis)
        assert is_ok is True
        assert issues == []

    def test_us_citizenship_required_is_incompatible(self):
        svc = JobAnalysisService()
        analysis = make_analysis(citizenship_required="US")
        is_ok, issues = svc.calculate_armenia_compatibility(analysis)
        assert is_ok is False
        assert any("citizenship" in i.lower() or "US" in i for i in issues)

    def test_eu_citizenship_required_is_incompatible(self):
        svc = JobAnalysisService()
        analysis = make_analysis(citizenship_required="EU")
        is_ok, issues = svc.calculate_armenia_compatibility(analysis)
        assert is_ok is False

    def test_us_only_location_is_incompatible(self):
        svc = JobAnalysisService()
        analysis = make_analysis(location_requirement="US Only")
        is_ok, issues = svc.calculate_armenia_compatibility(analysis)
        assert is_ok is False
        assert any("United States" in i or "US" in i for i in issues)

    def test_relocation_required_is_incompatible(self):
        svc = JobAnalysisService()
        analysis = make_analysis(location_requirement="Must relocate to San Francisco")
        is_ok, issues = svc.calculate_armenia_compatibility(analysis)
        assert is_ok is False

    def test_regular_office_visits_is_incompatible(self):
        svc = JobAnalysisService()
        analysis = make_analysis(office_visits="Regular")
        is_ok, issues = svc.calculate_armenia_compatibility(analysis)
        assert is_ok is False
        assert any("office" in i.lower() for i in issues)


# ---------------------------------------------------------------------------
# LLM failure fallback
# ---------------------------------------------------------------------------

class TestLLMFailureFallback:
    @pytest.mark.asyncio
    async def test_returns_default_analysis_on_llm_error(self, tmp_path):
        """If the LLM call fails, analyze_job should return a default analysis."""
        svc = JobAnalysisService()
        svc._cache_dir = tmp_path

        with patch(
            "backend.services.job_analysis.send_message",
            new_callable=AsyncMock,
            side_effect=Exception("LLM unavailable"),
        ):
            result = await svc.analyze_job("desc", ["Python"], use_cache=False)

        assert isinstance(result, JobAnalysis)
        assert result.recommendation == "Consider"
        assert any("failed" in flag.lower() for flag in result.red_flags)

    @pytest.mark.asyncio
    async def test_returns_default_analysis_on_invalid_json(self, tmp_path):
        """If the LLM returns non-JSON, analyze_job returns a default analysis."""
        svc = JobAnalysisService()
        svc._cache_dir = tmp_path

        with patch(
            "backend.services.job_analysis.send_message",
            new_callable=AsyncMock,
            return_value="Sorry, I cannot analyze this.",
        ):
            result = await svc.analyze_job("desc", ["Python"], use_cache=False)

        assert isinstance(result, JobAnalysis)
