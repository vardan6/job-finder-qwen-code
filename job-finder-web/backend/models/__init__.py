"""
Models Package

All models are imported here for easy access and database initialization.
"""
from backend.models.candidate import Candidate
from backend.models.job import Job, JobApplication
from backend.models.supporting import CandidateJobTitle, CandidateSkill, CandidatePreferences
from backend.models.llm_provider import LLMProvider, LLMModel
from backend.models.document import CandidateDocument, DocumentSection, DocumentParsePrompt, LLMFunctionMapping

__all__ = [
    "Candidate",
    "Job",
    "JobApplication",
    "CandidateJobTitle",
    "CandidateSkill",
    "CandidatePreferences",
    "LLMProvider",
    "LLMModel",
    "CandidateDocument",
    "DocumentSection",
    "DocumentParsePrompt",
    "LLMFunctionMapping",
]
