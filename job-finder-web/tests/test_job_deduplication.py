"""
Tests for job_deduplication.py

Pure logic — no LLM, no database, no external dependencies.
Job objects are created as plain in-memory instances (no ORM session needed).
"""
import pytest
from unittest.mock import MagicMock

from backend.services.job_deduplication import (
    JobDeduplicator,
    DeduplicationSignal,
    THRESHOLD_EXACT_MATCH,
    THRESHOLD_LIKELY_MATCH,
    THRESHOLD_POSSIBLE_MATCH,
    from_scraped_dict,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_job(
    title="Software Engineer",
    company="Acme Corp",
    location="Remote",
    platform="linkedin",
    platform_job_id=None,
    description_hash=None,
):
    """Create a lightweight mock Job object."""
    job = MagicMock()
    job.title = title
    job.company = company
    job.location = location
    job.platform = platform
    job.platform_job_id = platform_job_id
    job.description_hash = description_hash
    return job


# ---------------------------------------------------------------------------
# compute_description_hash
# ---------------------------------------------------------------------------

class TestComputeDescriptionHash:
    def test_same_description_same_hash(self):
        d = JobDeduplicator()
        assert d.compute_description_hash("Hello world") == d.compute_description_hash("Hello world")

    def test_different_descriptions_different_hash(self):
        d = JobDeduplicator()
        assert d.compute_description_hash("Job A") != d.compute_description_hash("Job B")

    def test_whitespace_normalization(self):
        """Extra whitespace should not affect the hash."""
        d = JobDeduplicator()
        h1 = d.compute_description_hash("Hello  world")
        h2 = d.compute_description_hash("Hello world")
        assert h1 == h2

    def test_case_normalization(self):
        """Hash should be case-insensitive."""
        d = JobDeduplicator()
        assert d.compute_description_hash("Python") == d.compute_description_hash("PYTHON")


# ---------------------------------------------------------------------------
# _calculate_combined_score — exact match signals
# ---------------------------------------------------------------------------

class TestCombinedScore:
    def test_description_hash_match_returns_100(self):
        d = JobDeduplicator()
        signal = DeduplicationSignal(description_hash_match=True)
        assert d._calculate_combined_score(signal) == 100

    def test_platform_id_match_returns_100(self):
        d = JobDeduplicator()
        signal = DeduplicationSignal(platform_job_id_match=True)
        assert d._calculate_combined_score(signal) == 100

    def test_weighted_average_formula(self):
        """Combined = title*0.4 + company*0.4 + location*0.2"""
        d = JobDeduplicator()
        signal = DeduplicationSignal(title_similarity=100, company_similarity=100, location_similarity=100)
        assert d._calculate_combined_score(signal) == 100

    def test_zero_similarity_is_zero(self):
        d = JobDeduplicator()
        signal = DeduplicationSignal(title_similarity=0, company_similarity=0, location_similarity=0)
        assert d._calculate_combined_score(signal) == 0


# ---------------------------------------------------------------------------
# calculate_similarity
# ---------------------------------------------------------------------------

class TestCalculateSimilarity:
    def test_identical_jobs_score_100(self):
        d = JobDeduplicator()
        job = make_job(description_hash="abc123", platform_job_id="j1")
        signal = d.calculate_similarity(job, job)
        assert signal.combined_score == 100

    def test_same_hash_is_exact_match(self):
        d = JobDeduplicator()
        j1 = make_job(description_hash="deadbeef")
        j2 = make_job(description_hash="deadbeef")
        signal = d.calculate_similarity(j1, j2)
        assert signal.description_hash_match is True
        assert signal.combined_score == 100

    def test_same_platform_id_is_exact_match(self):
        d = JobDeduplicator()
        j1 = make_job(platform="linkedin", platform_job_id="12345")
        j2 = make_job(platform="linkedin", platform_job_id="12345")
        signal = d.calculate_similarity(j1, j2)
        assert signal.platform_job_id_match is True
        assert signal.combined_score == 100

    def test_different_platform_same_job_id_not_matched(self):
        """Same job ID on different platforms should NOT be an exact match."""
        d = JobDeduplicator()
        j1 = make_job(platform="linkedin", platform_job_id="12345")
        j2 = make_job(platform="glassdoor", platform_job_id="12345")
        signal = d.calculate_similarity(j1, j2)
        assert signal.platform_job_id_match is False

    def test_completely_different_jobs_low_score(self):
        d = JobDeduplicator()
        j1 = make_job(title="Python Backend Engineer", company="AlphaCorp", location="Remote")
        j2 = make_job(title="UX Designer", company="BetaStudio", location="New York, NY")
        signal = d.calculate_similarity(j1, j2)
        assert signal.combined_score < THRESHOLD_POSSIBLE_MATCH

    def test_missing_location_uses_neutral_score(self):
        d = JobDeduplicator()
        j1 = make_job(location=None)
        j2 = make_job(location=None)
        signal = d.calculate_similarity(j1, j2)
        assert signal.location_similarity == 50


# ---------------------------------------------------------------------------
# is_duplicate
# ---------------------------------------------------------------------------

class TestIsDuplicate:
    def test_exact_hash_match_is_duplicate(self):
        d = JobDeduplicator()
        j1 = make_job(description_hash="abc")
        j2 = make_job(description_hash="abc")
        is_dup, _ = d.is_duplicate(j1, j2)
        assert is_dup is True

    def test_same_title_and_company_is_likely_duplicate(self):
        d = JobDeduplicator()
        j1 = make_job(title="Senior Python Engineer", company="TechCo", location="Remote")
        j2 = make_job(title="Senior Python Engineer", company="TechCo", location="Remote")
        is_dup, signal = d.is_duplicate(j1, j2)
        assert is_dup is True
        assert signal.combined_score >= THRESHOLD_LIKELY_MATCH

    def test_different_company_same_title_not_duplicate(self):
        d = JobDeduplicator()
        # Companies must be genuinely different strings — "CompanyA"/"CompanyB" score ~88%
        j1 = make_job(title="Software Engineer", company="Google")
        j2 = make_job(title="Software Engineer", company="Netflix")
        is_dup, signal = d.is_duplicate(j1, j2)
        # Title is the same but company is clearly different → combined score below 80
        assert is_dup is False


# ---------------------------------------------------------------------------
# filter_duplicates
# ---------------------------------------------------------------------------

class TestFilterDuplicates:
    def test_no_duplicates_returns_all(self):
        d = JobDeduplicator()
        jobs = [
            make_job(title="Python Dev", company="AlphaCorp", location="Remote"),
            make_job(title="Go Engineer", company="BetaCorp", location="Remote"),
            make_job(title="Frontend React", company="GammaCorp", location="Remote"),
        ]
        result = d.filter_duplicates(jobs, [])
        assert len(result) == 3

    def test_exact_hash_duplicates_filtered(self):
        d = JobDeduplicator()
        existing = [make_job(description_hash="hash1", title="Python Dev", company="AlphaCorp")]
        new_jobs = [
            make_job(description_hash="hash1", title="Python Dev", company="AlphaCorp"),  # duplicate
            make_job(description_hash="hash2", title="Go Engineer", company="BetaCorp"),  # unique
        ]
        result = d.filter_duplicates(new_jobs, existing)
        assert len(result) == 1
        assert result[0].title == "Go Engineer"

    def test_platform_id_duplicates_filtered(self):
        d = JobDeduplicator()
        existing = [make_job(platform="linkedin", platform_job_id="job_001", title="Dev", company="X")]
        new_jobs = [
            make_job(platform="linkedin", platform_job_id="job_001", title="Dev", company="X"),  # dup
            make_job(platform="linkedin", platform_job_id="job_002", title="SRE", company="Y"),  # unique
        ]
        result = d.filter_duplicates(new_jobs, existing)
        assert len(result) == 1

    def test_empty_new_jobs_returns_empty(self):
        d = JobDeduplicator()
        result = d.filter_duplicates([], [make_job()])
        assert result == []

    def test_bulk_deduplication(self):
        """10 jobs where 3 are hash duplicates of existing → 7 returned."""
        d = JobDeduplicator()
        existing = [
            make_job(description_hash=f"dup_{i}", title=f"Dup Job {i}", company="X")
            for i in range(3)
        ]
        new_jobs = [
            make_job(description_hash=f"dup_{i}", title=f"Dup Job {i}", company="X")
            for i in range(3)  # 3 duplicates
        ] + [
            make_job(description_hash=f"new_{i}", title=f"New Job {i}", company="Y")
            for i in range(7)  # 7 unique
        ]
        result = d.filter_duplicates(new_jobs, existing)
        assert len(result) == 7


class TestFromScrapedDict:
    """from_scraped_dict builds a transient, unpersisted Job for dedup comparison."""

    def test_maps_expected_fields(self):
        job = from_scraped_dict({
            "title": "Backend Engineer",
            "company": "Acme",
            "location": "Remote",
            "platform": "linkedin",
            "platform_job_id": "123",
            "description_hash": "abc",
        })
        assert job.title == "Backend Engineer"
        assert job.company == "Acme"
        assert job.location == "Remote"
        assert job.platform == "linkedin"
        assert job.platform_job_id == "123"
        assert job.description_hash == "abc"

    def test_missing_keys_default_to_empty_or_none(self):
        job = from_scraped_dict({})
        assert job.title == ""
        assert job.company == ""
        assert job.location == ""
        assert job.platform == ""
        assert job.platform_job_id is None
        assert job.description_hash is None

    def test_result_is_comparable_via_is_duplicate(self):
        d = JobDeduplicator()
        a = from_scraped_dict({"title": "Engineer", "company": "Acme", "description_hash": "same"})
        b = from_scraped_dict({"title": "Engineer", "company": "Acme", "description_hash": "same"})
        is_dup, _ = d.is_duplicate(a, b)
        assert is_dup is True
