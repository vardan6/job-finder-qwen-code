"""
Services Package - Business logic layer
"""
from backend.services.llm_service import (
    get_llm_for_function,
    call_llm,
    extract_json_from_response,
)
from backend.services.document_parser import (
    parse_document_content,
    get_candidate_prompt,
    reset_candidate_prompt_to_system,
)
from backend.services.job_title_parser import (
    parse_all_candidate_documents,
    save_job_titles_to_candidate,
    get_candidate_job_titles_with_sources,
)

__all__ = [
    # LLM Service
    "get_llm_for_function",
    "call_llm",
    "extract_json_from_response",
    # Document Parser
    "parse_document_content",
    "get_candidate_prompt",
    "reset_candidate_prompt_to_system",
    # Job Title Parser
    "parse_all_candidate_documents",
    "save_job_titles_to_candidate",
    "get_candidate_job_titles_with_sources",
]
