"""
Models Package

All models are imported here for easy access and database initialization.
"""
from backend.models.candidate import Candidate
from backend.models.user import User
from backend.models.job import Job, JobApplication, SearchRun, SearchRunJob
from backend.models.supporting import CandidateJobTitle, CandidateSkill, CandidatePreferences, ExtractionOccurrence
from backend.models.llm_provider import LLMProvider, LLMModel
from backend.models.document import CandidateDocument, DocumentSection, DocumentParsePrompt, GeneratedDocument
from backend.models.platform_account import PlatformAccount

__all__ = [
    "Candidate",
    "User",
    "Job",
    "JobApplication",
    "SearchRun",
    "SearchRunJob",
    "CandidateJobTitle",
    "CandidateSkill",
    "CandidatePreferences",
    "ExtractionOccurrence",
    "LLMProvider",
    "LLMModel",
    "CandidateDocument",
    "DocumentSection",
    "DocumentParsePrompt",
    "GeneratedDocument",
    "PlatformAccount",
]
